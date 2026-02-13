import json
import os
import re
import time
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

athena = boto3.client("athena")
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SQL_DIR = Path(__file__).parent / "sql"


def load_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text()


def parse_partition_name(partition_name: str) -> tuple[int, str]:
    """Parse 'season=2025/game_date=2025-03-27' into (2025, '2025-03-27')."""
    match = re.match(r"season=(\d+)/game_date=(\d{4}-\d{2}-\d{2})", partition_name)
    if not match:
        raise ValueError(
            f"Invalid partition_name: {partition_name}. "
            "Expected format: season=YYYY/game_date=YYYY-MM-DD"
        )
    return int(match.group(1)), match.group(2)


def run_query(sql: str) -> str:
    """Submit a query to Athena and wait for it to complete. Returns the query execution ID."""
    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": f"s3://{OUTPUT_BUCKET}/"},
    )
    execution_id: str = response["QueryExecutionId"]

    while True:
        result = athena.get_query_execution(QueryExecutionId=execution_id)
        state = result["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            return execution_id

        if state in ("FAILED", "CANCELLED"):
            reason = result["QueryExecution"]["Status"].get(
                "StateChangeReason", "Unknown"
            )
            raise RuntimeError(f"Query {state}: {reason}")

        time.sleep(2)


def get_query_row_count(execution_id: str) -> int:
    """Get the row count from a completed INSERT/MERGE query result.

    Athena returns counts in different places depending on the operation:
    - INSERT INTO Iceberg: count in ResultSet.Rows[1]
    - MERGE INTO Iceberg: count in UpdateCount (Rows is empty)
    """
    result = athena.get_query_results(QueryExecutionId=execution_id)
    update_count = result.get("UpdateCount", 0)
    if update_count:
        return update_count
    rows = result["ResultSet"]["Rows"]
    if len(rows) >= 2:
        return int(rows[1]["Data"][0]["VarCharValue"])
    return 0


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    partition_name = event["partition_name"]
    season, game_date = parse_partition_name(partition_name)

    metrics.add_dimension(name="season", value=str(season))

    fmt = {"season": season, "game_date": game_date}

    steps = [
        ("clear_staging", "silver_clear_partition_from_staging_table.sql"),
        ("load_partition", "silver_load_partition_into_staging_table.sql"),
        ("merge_partition", "silver_merge_partition_into_canonical_table.sql"),
        ("clear_staging", "silver_clear_partition_from_staging_table.sql"),
    ]

    records_loaded = 0
    records_merged = 0
    results = {}
    for step_name, sql_file in steps:
        sql = load_sql(sql_file).format(**fmt)
        print(f"Running {step_name}: {sql_file}")
        execution_id = run_query(sql)
        results[step_name] = execution_id
        print(f"  Completed: {execution_id}")

        if step_name == "load_partition":
            records_loaded = get_query_row_count(execution_id)
            print(f"  Records loaded into staging: {records_loaded}")

        if step_name == "merge_partition":
            records_merged = get_query_row_count(execution_id)
            print(f"  Records merged into canonical: {records_merged}")

    metrics.add_metric(
        name="RecordsLoaded", unit=MetricUnit.Count, value=records_loaded
    )
    metrics.add_metric(
        name="RecordsMerged", unit=MetricUnit.Count, value=records_merged
    )
    metrics.add_metric(name="PartitionsInserted", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "partition_name": partition_name,
                "season": season,
                "game_date": game_date,
                "records_loaded": records_loaded,
                "records_merged": records_merged,
                "results": results,
            }
        ),
    }
