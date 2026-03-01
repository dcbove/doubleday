"""Lambda handler for DynamoDB load — event parsing, metrics, and response building."""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.pipeline.dynamodb_load.pipeline import load_to_dynamodb

athena = boto3.client("athena")
dynamodb = boto3.resource("dynamodb")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SERVING_TABLE_NAME = os.environ["SERVING_TABLE_NAME"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Load gold data for a single entity type and season into DynamoDB."""
    entity_type = event["entity_type"]
    season = int(event["season"])

    metrics.add_dimension(name="entity_type", value=entity_type)
    metrics.add_dimension(name="season", value=str(season))

    table = dynamodb.Table(SERVING_TABLE_NAME)
    result = load_to_dynamodb(athena, table, DATABASE, OUTPUT_BUCKET, SQL_DIR, entity_type, season)

    metrics.add_metric(name="RecordsLoaded", unit=MetricUnit.Count, value=result.records_loaded)
    metrics.add_metric(name="RecordsDeleted", unit=MetricUnit.Count, value=result.records_deleted)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "entity_type": entity_type,
                "season": season,
                "records_loaded": result.records_loaded,
                "records_deleted": result.records_deleted,
            }
        ),
    }
