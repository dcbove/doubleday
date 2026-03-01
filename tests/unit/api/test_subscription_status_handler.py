"""Unit tests for the subscription status handler (doubleday.api.subscription_status.handler).

Tests the GET /subscriptions/status endpoint which returns the current
subscription state for the authenticated user.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.subscription_status.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-subscription-status"
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


class TestSubscriptionStatusHandler:
    """Tests for the subscription status handler."""

    @patch("doubleday.api.subscription_status.handler.dynamodb")
    def test_active_subscription_returns_status(self, mock_dynamodb, lambda_context):
        """Active subscription returns full status details."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "USER#user-123",
                "status": "active",
                "tier": "basic",
                "current_period_end": "2025-01-01T00:00:00+00:00",
            },
        }

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "active"
        assert body["tier"] == "basic"
        assert body["has_subscription"] is True

    @patch("doubleday.api.subscription_status.handler.dynamodb")
    def test_no_entitlement_returns_inactive(self, mock_dynamodb, lambda_context):
        """No entitlement record returns inactive status."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "inactive"
        assert body["has_subscription"] is False

    def test_missing_principal_returns_401(self, lambda_context):
        """Missing principalId returns 401."""
        event = {"requestContext": {"authorizer": {}}}

        result = handler(event, lambda_context)

        assert result["statusCode"] == 401
