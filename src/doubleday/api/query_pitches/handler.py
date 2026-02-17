"""Lambda handler for query_pitches — API Gateway proxy integration."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.api.query_pitches.query import query_pitches

athena = boto3.client("athena")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build an API Gateway error response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle GET /pitchers/{pitcher_id}/pitches requests."""
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    pitcher_id_str = path_params.get("pitcher_id")
    if not pitcher_id_str:
        return _error_response(400, "Missing pitcher_id path parameter")

    try:
        pitcher_id = int(pitcher_id_str)
    except ValueError:
        return _error_response(400, "pitcher_id must be an integer")

    season_str = query_params.get("season")
    if not season_str:
        return _error_response(400, "Missing required query parameter: season")

    try:
        season = int(season_str)
    except ValueError:
        return _error_response(400, "season must be an integer")

    pitch_type = query_params.get("pitch_type")

    metrics.add_dimension(name="pitcher", value=str(pitcher_id))
    metrics.add_dimension(name="season", value=str(season))

    result = query_pitches(athena, DATABASE, OUTPUT_BUCKET, SQL_DIR, pitcher_id, season, pitch_type)

    metrics.add_metric(name="PitchTypesReturned", unit=MetricUnit.Count, value=len(result.pitches))

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(asdict(result)),
    }
