"""Lambda handler for stripe_webhook — API Gateway proxy integration.

Receives Stripe webhook events, verifies their signature, and updates the
DynamoDB entitlements table to reflect subscription state changes.

This endpoint has NO JWT authorization — it is protected by Stripe webhook
signature verification instead.

Environment variables (read at module level, set by Terraform):
    STRIPE_SECRET_KEY: Stripe secret API key.
    STRIPE_WEBHOOK_SECRET: Stripe webhook signing secret (whsec_...).
    ENTITLEMENTS_TABLE_NAME: DynamoDB table for user entitlements.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3
import stripe
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
metrics = Metrics()

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
ENTITLEMENTS_TABLE_NAME = os.environ["ENTITLEMENTS_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Stripe-Signature",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build an API Gateway error response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _get_cognito_sub_from_customer(customer_id: str) -> str | None:
    """Retrieve the cognito_sub from Stripe customer metadata.

    Args:
        customer_id: Stripe customer ID.

    Returns:
        The cognito_sub string, or None if not found.
    """
    customer = stripe.Customer.retrieve(customer_id)
    cognito_sub: str | None = customer.get("metadata", {}).get("cognito_sub")
    return cognito_sub


def _handle_checkout_completed(session: dict[str, Any], table: Any) -> None:
    """Handle checkout.session.completed — create or activate an entitlement.

    Args:
        session: Stripe Checkout Session object.
        table: DynamoDB Table resource.
    """
    cognito_sub = session.get("client_reference_id")
    if not cognito_sub:
        logger.warning("checkout.session.completed missing client_reference_id")
        return

    now = datetime.now(UTC).isoformat()
    table.put_item(
        Item={
            "PK": f"USER#{cognito_sub}",
            "status": "active",
            "tier": "basic",
            "stripe_customer_id": session["customer"],
            "stripe_subscription_id": session.get("subscription", ""),
            "email": session.get("customer_email", ""),
            "created_at": now,
            "updated_at": now,
        },
    )
    logger.info("Entitlement activated", extra={"cognito_sub": cognito_sub})


def _handle_subscription_updated(subscription: dict[str, Any], table: Any) -> None:
    """Handle customer.subscription.updated — sync subscription state.

    Args:
        subscription: Stripe Subscription object.
        table: DynamoDB Table resource.
    """
    cognito_sub = _get_cognito_sub_from_customer(subscription["customer"])
    if not cognito_sub:
        logger.warning("Could not resolve cognito_sub for customer", extra={"customer": subscription["customer"]})
        return

    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "inactive",
        "incomplete_expired": "inactive",
        "trialing": "active",
        "paused": "inactive",
    }
    entitlement_status = status_map.get(subscription["status"], "inactive")
    now = datetime.now(UTC).isoformat()

    table.update_item(
        Key={"PK": f"USER#{cognito_sub}"},
        UpdateExpression="SET #status = :status, current_period_end = :period_end, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": entitlement_status,
            ":period_end": datetime.fromtimestamp(subscription["current_period_end"], tz=UTC).isoformat(),
            ":now": now,
        },
    )
    logger.info(
        "Entitlement updated",
        extra={"cognito_sub": cognito_sub, "status": entitlement_status},
    )


def _handle_subscription_deleted(subscription: dict[str, Any], table: Any) -> None:
    """Handle customer.subscription.deleted — mark entitlement as canceled.

    Args:
        subscription: Stripe Subscription object.
        table: DynamoDB Table resource.
    """
    cognito_sub = _get_cognito_sub_from_customer(subscription["customer"])
    if not cognito_sub:
        logger.warning("Could not resolve cognito_sub for customer", extra={"customer": subscription["customer"]})
        return

    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"PK": f"USER#{cognito_sub}"},
        UpdateExpression="SET #status = :status, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "canceled", ":now": now},
    )
    logger.info("Entitlement canceled", extra={"cognito_sub": cognito_sub})


def _handle_payment_failed(invoice: dict[str, Any], table: Any) -> None:
    """Handle invoice.payment_failed — mark entitlement as past_due.

    Args:
        invoice: Stripe Invoice object.
        table: DynamoDB Table resource.
    """
    cognito_sub = _get_cognito_sub_from_customer(invoice["customer"])
    if not cognito_sub:
        logger.warning("Could not resolve cognito_sub for customer", extra={"customer": invoice["customer"]})
        return

    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"PK": f"USER#{cognito_sub}"},
        UpdateExpression="SET #status = :status, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "past_due", ":now": now},
    )
    logger.info("Entitlement marked past_due", extra={"cognito_sub": cognito_sub})


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle POST /stripe/webhook requests.

    Args:
        event: API Gateway proxy event with Stripe webhook payload.
        context: Lambda context (unused).

    Returns:
        API Gateway proxy response.
    """
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")

    sig_header = (event.get("headers") or {}).get("Stripe-Signature", "")

    try:
        stripe_event = stripe.Webhook.construct_event(body, sig_header, WEBHOOK_SECRET)
    except ValueError:
        logger.warning("Invalid webhook payload")
        return _error_response(400, "Invalid payload")
    except stripe.SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        return _error_response(400, "Invalid signature")

    event_type = stripe_event["type"]
    metrics.add_dimension(name="event_type", value=event_type)
    logger.info("Webhook received", extra={"event_type": event_type})

    table = dynamodb.Table(ENTITLEMENTS_TABLE_NAME)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(stripe_event["data"]["object"], table)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(stripe_event["data"]["object"], table)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(stripe_event["data"]["object"], table)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(stripe_event["data"]["object"], table)
    else:
        logger.info("Unhandled event type", extra={"event_type": event_type})

    metrics.add_metric(name="WebhookProcessed", unit=MetricUnit.Count, value=1)

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"received": True}),
    }
