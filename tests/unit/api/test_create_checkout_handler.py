"""Unit tests for the create checkout handler (doubleday.api.create_checkout.handler).

Tests the POST /subscriptions/checkout endpoint which creates a Stripe Checkout
Session for subscription signup.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_PRICE_ID", "price_test_fake")
os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("FRONTEND_URL", "https://example.com")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.create_checkout.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-create-checkout"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _event(principal_id="user-123"):
    """Build an API Gateway proxy event with authorizer context."""
    return {
        "requestContext": {
            "authorizer": {"principalId": principal_id},
        },
    }


class TestCreateCheckoutHandler:
    """Tests for the create checkout handler."""

    @patch("doubleday.api.create_checkout.handler.dynamodb")
    @patch("doubleday.api.create_checkout.handler.stripe")
    def test_creates_checkout_session_for_new_user(self, mock_stripe, mock_dynamodb, lambda_context):
        """New user gets a Stripe customer created and a checkout session."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        mock_stripe.Customer.create.return_value = {"id": "cus_new"}
        mock_stripe.checkout.Session.create.return_value = MagicMock(url="https://checkout.stripe.com/session")
        mock_stripe.StripeError = Exception

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checkout_url"] == "https://checkout.stripe.com/session"
        mock_stripe.Customer.create.assert_called_once()

    @patch("doubleday.api.create_checkout.handler.dynamodb")
    @patch("doubleday.api.create_checkout.handler.stripe")
    def test_uses_existing_stripe_customer(self, mock_stripe, mock_dynamodb, lambda_context):
        """Existing user with stripe_customer_id reuses it."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user-123", "stripe_customer_id": "cus_existing"},
        }

        mock_stripe.checkout.Session.create.return_value = MagicMock(url="https://checkout.stripe.com/session")
        mock_stripe.StripeError = Exception

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        mock_stripe.Customer.create.assert_not_called()
        session_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert session_kwargs["customer"] == "cus_existing"

    def test_missing_principal_returns_401(self, lambda_context):
        """Missing principalId returns 401."""
        event = {"requestContext": {"authorizer": {}}}

        result = handler(event, lambda_context)

        assert result["statusCode"] == 401
