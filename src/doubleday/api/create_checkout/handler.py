"""Lambda handler for create_checkout — API Gateway proxy integration.

Creates a Stripe Checkout Session for subscription signup. Links the Cognito
user identity to the Stripe customer via client_reference_id and customer
metadata.

Environment variables (read at module level, set by Terraform):
    STRIPE_SECRET_KEY: Stripe secret API key.
    STRIPE_PRICE_ID: Stripe Price ID for the subscription plan.
    ENTITLEMENTS_TABLE_NAME: DynamoDB table for user entitlements.
    FRONTEND_URL: Frontend base URL for redirect after checkout.
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
STRIPE_PRICE_ID = os.environ["STRIPE_PRICE_ID"]
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


def _get_or_create_stripe_customer(table: Any, cognito_sub: str) -> str:
    """Get existing Stripe customer ID or create a new one.

    Args:
        table: DynamoDB Table resource for entitlements.
        cognito_sub: The user's Cognito sub claim.

    Returns:
        Stripe customer ID.
    """
    response = table.get_item(Key={"PK": f"USER#{cognito_sub}"})
    item = response.get("Item")
    if item and item.get("stripe_customer_id"):
        customer_id: str = item["stripe_customer_id"]
        return customer_id

    customer = stripe.Customer.create(metadata={"cognito_sub": cognito_sub})
    new_id: str = customer["id"]
    return new_id


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle POST /subscriptions/checkout requests.

    Args:
        event: API Gateway proxy event.
        context: Lambda context (unused).

    Returns:
        API Gateway proxy response with checkout_url.
    """
    principal_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
    if not principal_id:
        return _error_response(401, "Unauthorized")

    table = dynamodb.Table(ENTITLEMENTS_TABLE_NAME)

    try:
        customer_id = _get_or_create_stripe_customer(table, principal_id)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/subscription/success",
            cancel_url=f"{FRONTEND_URL}/subscription/cancel",
            client_reference_id=principal_id,
        )

        metrics.add_metric(name="CheckoutSessionCreated", unit=MetricUnit.Count, value=1)
        logger.info("Checkout session created", extra={"principal": principal_id})

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"checkout_url": session.url}),
        }
    except stripe.StripeError as e:
        logger.exception("Stripe error creating checkout session")
        return _error_response(502, f"Payment service error: {e!s}")
