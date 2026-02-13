"""Lambda handler for gold load — event parsing, metrics, and response building."""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.lambdas.gold_load.pipeline import load_table

athena = boto3.client("athena")
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Load a single gold table partition for the given season."""
    table_name = event["table_name"]
    season = int(event["season"])

    metrics.add_dimension(name="table", value=table_name)
    metrics.add_dimension(name="season", value=str(season))

    result = load_table(athena, DATABASE, OUTPUT_BUCKET, SQL_DIR, table_name, season)

    metrics.add_metric(
        name="RecordsInserted", unit=MetricUnit.Count, value=result.records_inserted
    )
    metrics.add_metric(name="TablesLoaded", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "table_name": table_name,
                "season": season,
                "records_inserted": result.records_inserted,
                "results": result.results,
            }
        ),
    }
