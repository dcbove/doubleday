"""Lambda handler for customer_portal — API Gateway proxy integration.

Creates a Stripe Billing Portal session so users can manage their subscription
(cancel, update payment method, view invoices).

Environment variables (read at module level, set by Terraform):
    STRIPE_SECRET_KEY: Stripe secret API key.
    ENTITLEMENTS_TABLE_NAME: DynamoDB table for user entitlements.
    FRONTEND_URL: Frontend base URL for return after portal.
"""

import json
import os
from typing import Any

import boto3
import stripe
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
metrics = Metrics()

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
ENTITLEMENTS_TABLE_NAME = os.environ["ENTITLEMENTS_TABLE_NAME"]
FRONTEND_URL = os.environ["FRONTEND_URL"]

dynamodb = boto3.resource("dynamodb")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
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
    """Handle POST /subscriptions/portal requests.

    Args:
        event: API Gateway proxy event.
        context: Lambda context (unused).

    Returns:
        API Gateway proxy response with portal_url.
    """
    principal_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
    if not principal_id:
        return _error_response(401, "Unauthorized")

    table = dynamodb.Table(ENTITLEMENTS_TABLE_NAME)
    response = table.get_item(Key={"PK": f"USER#{principal_id}"})
    item = response.get("Item")

    if not item or not item.get("stripe_customer_id"):
        return _error_response(404, "No subscription found")

    try:
        session = stripe.billing_portal.Session.create(
            customer=item["stripe_customer_id"],
            return_url=f"{FRONTEND_URL}/subscription",
        )

        metrics.add_metric(name="PortalSessionCreated", unit=MetricUnit.Count, value=1)
        logger.info("Portal session created", extra={"principal": principal_id})

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"portal_url": session.url}),
        }
    except stripe.StripeError as e:
        logger.exception("Stripe error creating portal session")
        return _error_response(502, f"Payment service error: {e!s}")
