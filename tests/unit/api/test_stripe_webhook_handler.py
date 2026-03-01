"""Unit tests for the Stripe webhook handler (doubleday.api.stripe_webhook.handler).

The webhook handler receives Stripe events, verifies their signature, and
updates the DynamoDB entitlements table. These tests mock the Stripe SDK and
DynamoDB to test event routing and entitlement writes.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_fake")
os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.stripe_webhook.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-stripe-webhook"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _webhook_event(body, sig="valid-sig"):
    """Build an API Gateway proxy event for the webhook."""
    return {
        "body": body,
        "headers": {"Stripe-Signature": sig},
        "isBase64Encoded": False,
    }


class TestStripeWebhookHandler:
    """Tests for the Stripe webhook handler's event routing."""

    @patch("doubleday.api.stripe_webhook.handler.dynamodb")
    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_checkout_completed_creates_entitlement(self, mock_stripe, mock_dynamodb, lambda_context):
        """checkout.session.completed writes an active entitlement."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_stripe.Webhook.construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": "cognito-sub-123",
                    "customer": "cus_abc",
                    "subscription": "sub_xyz",
                    "customer_email": "user@example.com",
                },
            },
        }

        body = json.dumps({"type": "checkout.session.completed"})
        result = handler(_webhook_event(body), lambda_context)

        assert result["statusCode"] == 200
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args.kwargs["Item"]
        assert item["PK"] == "USER#cognito-sub-123"
        assert item["status"] == "active"
        assert item["stripe_customer_id"] == "cus_abc"

    @patch("doubleday.api.stripe_webhook.handler.dynamodb")
    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_subscription_updated_updates_status(self, mock_stripe, mock_dynamodb, lambda_context):
        """customer.subscription.updated updates entitlement status."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "cognito-sub-456"},
        }
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_def",
                    "status": "past_due",
                    "current_period_end": 1700000000,
                },
            },
        }

        body = json.dumps({"type": "customer.subscription.updated"})
        result = handler(_webhook_event(body), lambda_context)

        assert result["statusCode"] == 200
        mock_table.update_item.assert_called_once()
        kwargs = mock_table.update_item.call_args.kwargs
        assert kwargs["Key"] == {"PK": "USER#cognito-sub-456"}
        assert kwargs["ExpressionAttributeValues"][":status"] == "past_due"

    @patch("doubleday.api.stripe_webhook.handler.dynamodb")
    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_subscription_deleted_cancels_entitlement(self, mock_stripe, mock_dynamodb, lambda_context):
        """customer.subscription.deleted sets status to canceled."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "cognito-sub-789"},
        }
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": "cus_ghi",
                    "status": "canceled",
                },
            },
        }

        body = json.dumps({"type": "customer.subscription.deleted"})
        result = handler(_webhook_event(body), lambda_context)

        assert result["statusCode"] == 200
        kwargs = mock_table.update_item.call_args.kwargs
        assert kwargs["ExpressionAttributeValues"][":status"] == "canceled"

    @patch("doubleday.api.stripe_webhook.handler.dynamodb")
    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_payment_failed_sets_past_due(self, mock_stripe, mock_dynamodb, lambda_context):
        """invoice.payment_failed sets status to past_due."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "cognito-sub-101"},
        }
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {"customer": "cus_jkl"},
            },
        }

        body = json.dumps({"type": "invoice.payment_failed"})
        result = handler(_webhook_event(body), lambda_context)

        assert result["statusCode"] == 200
        kwargs = mock_table.update_item.call_args.kwargs
        assert kwargs["ExpressionAttributeValues"][":status"] == "past_due"

    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_invalid_signature_returns_400(self, mock_stripe, lambda_context):
        """Invalid Stripe signature returns 400."""
        mock_stripe.SignatureVerificationError = type("SignatureVerificationError", (Exception,), {})
        mock_stripe.Webhook.construct_event.side_effect = mock_stripe.SignatureVerificationError("bad sig")

        result = handler(_webhook_event("body", sig="bad-sig"), lambda_context)

        assert result["statusCode"] == 400

    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_invalid_payload_returns_400(self, mock_stripe, lambda_context):
        """Invalid payload returns 400."""
        mock_stripe.SignatureVerificationError = type("SignatureVerificationError", (Exception,), {})
        mock_stripe.Webhook.construct_event.side_effect = ValueError("bad payload")

        result = handler(_webhook_event("not-json"), lambda_context)

        assert result["statusCode"] == 400

    @patch("doubleday.api.stripe_webhook.handler.dynamodb")
    @patch("doubleday.api.stripe_webhook.handler.stripe")
    def test_unhandled_event_type_returns_200(self, mock_stripe, mock_dynamodb, lambda_context):
        """Unhandled event types still return 200 (acknowledged)."""
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "some.other.event",
            "data": {"object": {}},
        }

        result = handler(_webhook_event("body"), lambda_context)

        assert result["statusCode"] == 200
