"""Lambda handler for catalog — API Gateway proxy integration."""

import json
import os
from dataclasses import asdict
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from doubleday.api.catalog.query import get_manifest

s3 = boto3.client("s3")
logger = Logger()
metrics = Metrics()

FRONTEND_BUCKET = os.environ["FRONTEND_BUCKET"]

VALID_ROLES = {"pitchers", "batters"}

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
    """Handle GET /catalogs/{role} requests."""
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    role = path_params.get("role")
    if not role:
        return _error_response(400, "Missing role path parameter")

    if role not in VALID_ROLES:
        return _error_response(400, f"role must be one of: {', '.join(sorted(VALID_ROLES))}")

    season_str = query_params.get("season")
    if not season_str:
        return _error_response(400, "Missing required query parameter: season")

    try:
        season = int(season_str)
    except ValueError:
        return _error_response(400, "season must be an integer")

    if not (1000 <= season <= 9999):
        return _error_response(400, "season must be a 4-digit year")

    try:
        result = get_manifest(s3, FRONTEND_BUCKET, season, role)
    except FileNotFoundError:
        return _error_response(404, f"No catalog found for {role} season {season}")

    metrics.add_metric(name="ManifestServed", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(asdict(result)),
    }
