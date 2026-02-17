"""Lambda handler for silver load — event parsing, metrics, and response building."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.pipeline.silver_load.pipeline import load_partition

athena = boto3.client("athena")
s3 = boto3.client("s3")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
LAKEHOUSE_BUCKET = os.environ["LAKEHOUSE_BUCKET"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Load a single silver partition, emit metrics, and return results."""
    season = event["season"]
    game_date = event["game_date"]
    batch_id = event["batch_id"]

    metrics.add_dimension(name="season", value=str(season))

    try:
        result = load_partition(athena, DATABASE, OUTPUT_BUCKET, SQL_DIR, season, game_date, batch_id)
    except Exception as exc:
        failure_record = {
            "batch_id": batch_id,
            "season": season,
            "game_date": game_date,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        s3.put_object(
            Bucket=LAKEHOUSE_BUCKET,
            Key=f"failures/silver_load/{batch_id}/{game_date}.json",
            Body=json.dumps(failure_record),
        )
        logger.error(
            "Silver load failed",
            extra={
                "batch_id": batch_id,
                "game_date": game_date,
                "season": season,
                "error": str(exc),
            },
        )
        metrics.add_metric(name="SilverLoadFailed", unit=MetricUnit.Count, value=1)
        raise

    metrics.add_metric(name="RecordsLoaded", unit=MetricUnit.Count, value=result.records_loaded)
    metrics.add_metric(name="RecordsInserted", unit=MetricUnit.Count, value=result.records_inserted)
    metrics.add_metric(name="PartitionsInserted", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "season": season,
                "game_date": game_date,
                "records_loaded": result.records_loaded,
                "records_inserted": result.records_inserted,
                "results": result.results,
            }
        ),
    }
