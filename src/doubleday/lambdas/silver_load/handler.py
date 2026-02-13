"""Lambda handler for silver load — event parsing, metrics, and response building."""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

from doubleday.lambdas.silver_load.pipeline import (
    load_partition,
    parse_partition_name,
)

athena = boto3.client("athena")
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SQL_DIR = Path(__file__).parent / "sql"


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Load a single silver partition, emit metrics, and return results."""
    partition_name = event["partition_name"]
    season, game_date = parse_partition_name(partition_name)

    metrics.add_dimension(name="season", value=str(season))

    result = load_partition(athena, DATABASE, OUTPUT_BUCKET, SQL_DIR, season, game_date)

    metrics.add_metric(
        name="RecordsLoaded", unit=MetricUnit.Count, value=result.records_loaded
    )
    metrics.add_metric(
        name="RecordsMerged", unit=MetricUnit.Count, value=result.records_merged
    )
    metrics.add_metric(name="PartitionsInserted", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "partition_name": partition_name,
                "season": season,
                "game_date": game_date,
                "records_loaded": result.records_loaded,
                "records_merged": result.records_merged,
                "results": result.results,
            }
        ),
    }
