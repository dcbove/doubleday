"""Lambda handler for clear_staging — delete all staging rows for a batch."""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.util.athena import run_query

athena = boto3.client("athena")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Delete all staging rows for the given batch_id."""
    batch_id = event["batch_id"]

    sql_path = SQL_DIR / "silver_clear_partition_from_staging_table.sql"
    sql = sql_path.read_text().format(batch_id=batch_id)

    logger.info("Clearing staging", extra={"batch_id": batch_id})
    execution_id = run_query(athena, sql, DATABASE, OUTPUT_BUCKET)
    logger.info(
        "Staging cleared",
        extra={"batch_id": batch_id, "execution_id": execution_id},
    )

    metrics.add_metric(name="StagingCleared", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "batch_id": batch_id,
                "execution_id": execution_id,
            }
        ),
    }
