"""Lambda handler for subscription_status — API Gateway proxy integration.

Returns the current subscription status for the authenticated user by looking
up their entitlement record in DynamoDB.

Environment variables (read at module level, set by Terraform):
    ENTITLEMENTS_TABLE_NAME: DynamoDB table for user entitlements.
"""

import json
import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics

logger = Logger()
metrics = Metrics()

ENTITLEMENTS_TABLE_NAME = os.environ["ENTITLEMENTS_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")

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
    """Handle GET /subscriptions/status requests.

    Args:
        event: API Gateway proxy event.
        context: Lambda context (unused).

    Returns:
        API Gateway proxy response with subscription status.
    """
    principal_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
    if not principal_id:
        return _error_response(401, "Unauthorized")

    table = dynamodb.Table(ENTITLEMENTS_TABLE_NAME)
    response = table.get_item(Key={"PK": f"USER#{principal_id}"})
    item = response.get("Item")

    if not item:
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {
                    "status": "inactive",
                    "tier": None,
                    "current_period_end": None,
                    "has_subscription": False,
                }
            ),
        }

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {
                "status": item.get("status", "inactive"),
                "tier": item.get("tier"),
                "current_period_end": item.get("current_period_end"),
                "has_subscription": True,
            }
        ),
    }
