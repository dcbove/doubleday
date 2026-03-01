"""Unit tests for the customer portal handler (doubleday.api.customer_portal.handler).

Tests the POST /subscriptions/portal endpoint which creates a Stripe Billing
Portal session for subscription management.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("FRONTEND_URL", "https://example.com")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.customer_portal.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-customer-portal"
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


class TestCustomerPortalHandler:
    """Tests for the customer portal handler."""

    @patch("doubleday.api.customer_portal.handler.dynamodb")
    @patch("doubleday.api.customer_portal.handler.stripe")
    def test_creates_portal_session(self, mock_stripe, mock_dynamodb, lambda_context):
        """User with stripe_customer_id gets a portal session URL."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user-123", "stripe_customer_id": "cus_abc"},
        }

        mock_stripe.billing_portal.Session.create.return_value = MagicMock(url="https://billing.stripe.com/portal")
        mock_stripe.StripeError = Exception

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["portal_url"] == "https://billing.stripe.com/portal"

    @patch("doubleday.api.customer_portal.handler.dynamodb")
    def test_no_subscription_returns_404(self, mock_dynamodb, lambda_context):
        """User with no entitlement record returns 404."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 404

    def test_missing_principal_returns_401(self, lambda_context):
        """Missing principalId returns 401."""
        event = {"requestContext": {"authorizer": {}}}

        result = handler(event, lambda_context)

        assert result["statusCode"] == 401
