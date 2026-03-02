"""Unit tests for the query_pitches handler (doubleday.api.query_pitches.handler).

Tests the REQUIRE_SUBSCRIPTION flag: when True, unsubscribed users receive 403;
when False, the subscription check is skipped and data is served to all
authenticated users. Default (env var unset) fails secure.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("SERVING_TABLE_NAME", "test-serving")
os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.query_pitches.handler import handler  # noqa: E402
from doubleday.api.query_pitches.query import QueryResult  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-query-pitches"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _event(principal_id="user-123", pitcher_id="12345", season="2025"):
    """Build an API Gateway proxy event for GET /pitchers/{id}/pitches."""
    return {
        "requestContext": {"authorizer": {"principalId": principal_id}},
        "pathParameters": {"pitcher_id": pitcher_id},
        "queryStringParameters": {"season": season},
    }


class TestRequireSubscriptionEnabled:
    """Tests when REQUIRE_SUBSCRIPTION is True."""

    @patch("doubleday.api.query_pitches.handler.REQUIRE_SUBSCRIPTION", True)
    @patch("doubleday.api.query_pitches.handler.dynamodb")
    def test_unsubscribed_user_returns_403(self, mock_dynamodb, lambda_context):
        """Unsubscribed user gets 403 when subscription is required."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 403
        body = json.loads(result["body"])
        assert body["error"] == "Active subscription required"

    @patch("doubleday.api.query_pitches.handler.REQUIRE_SUBSCRIPTION", True)
    @patch("doubleday.api.query_pitches.handler.query_pitches")
    @patch("doubleday.api.query_pitches.handler.dynamodb")
    def test_subscribed_user_returns_200(self, mock_dynamodb, mock_query, lambda_context):
        """Subscribed user gets data when subscription is required."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user-123", "status": "active"},
        }
        mock_query.return_value = QueryResult(pitcher=12345, season=2025)

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200


class TestRequireSubscriptionDisabled:
    """Tests when REQUIRE_SUBSCRIPTION is False."""

    @patch("doubleday.api.query_pitches.handler.REQUIRE_SUBSCRIPTION", False)
    @patch("doubleday.api.query_pitches.handler.query_pitches")
    @patch("doubleday.api.query_pitches.handler.dynamodb")
    def test_unsubscribed_user_returns_200(self, mock_dynamodb, mock_query, lambda_context):
        """Unsubscribed user gets data when subscription is not required."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_query.return_value = QueryResult(pitcher=12345, season=2025)

        result = handler(_event(), lambda_context)

        assert result["statusCode"] == 200
        mock_table.get_item.assert_not_called()


class TestDefaultRequireSubscription:
    """Tests that the default (env var unset) fails secure."""

    def test_default_requires_subscription(self):
        """When REQUIRE_SUBSCRIPTION is unset, it defaults to True."""
        saved = os.environ.pop("REQUIRE_SUBSCRIPTION", None)
        try:
            import importlib

            import doubleday.api.query_pitches.handler as mod

            importlib.reload(mod)
            assert mod.REQUIRE_SUBSCRIPTION is True
        finally:
            if saved is not None:
                os.environ["REQUIRE_SUBSCRIPTION"] = saved
