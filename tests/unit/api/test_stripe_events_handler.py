"""Unit tests for the Stripe EventBridge handler."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("ENTITLEMENTS_TABLE_NAME", "test-entitlements")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Doubleday")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.api.stripe_events.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.function_name = "test-stripe-events"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _eventbridge_event(detail_type, stripe_object):
    """Build an EventBridge event with Stripe data."""
    return {
        "version": "0",
        "id": "test-event-id",
        "source": "aws.partner/stripe.com/acct_123/evtdst_456",
        "detail-type": detail_type,
        "detail": {
            "id": "evt_test",
            "type": detail_type,
            "data": {"object": stripe_object},
        },
    }


class TestCheckoutCompleted:
    """Tests for checkout.session.completed events."""

    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_creates_entitlement(self, mock_dynamodb, lambda_context):
        """Checkout completion creates an entitlement record."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        event = _eventbridge_event(
            "checkout.session.completed",
            {
                "client_reference_id": "abc-123",
                "customer": "cus_test",
                "subscription": "sub_test",
                "customer_email": "test@example.com",
            },
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        assert result["event_type"] == "checkout.session.completed"
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#abc-123"
        assert item["status"] == "active"
        assert item["stripe_customer_id"] == "cus_test"

    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_missing_client_reference_id(self, mock_dynamodb, lambda_context):
        """Checkout without client_reference_id skips entitlement creation."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        event = _eventbridge_event(
            "checkout.session.completed",
            {"customer": "cus_test"},
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        mock_table.put_item.assert_not_called()


class TestSubscriptionUpdated:
    """Tests for customer.subscription.updated events."""

    @patch("doubleday.api.stripe_events.handler.stripe")
    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_updates_status(self, mock_dynamodb, mock_stripe, lambda_context):
        """Subscription update syncs status to entitlements table."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "abc-123"},
        }

        event = _eventbridge_event(
            "customer.subscription.updated",
            {
                "customer": "cus_test",
                "status": "active",
                "current_period_end": 1700000000,
            },
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        mock_table.update_item.assert_called_once()
        update_args = mock_table.update_item.call_args[1]
        assert update_args["Key"] == {"PK": "USER#abc-123"}
        assert update_args["ExpressionAttributeValues"][":status"] == "active"


class TestSubscriptionDeleted:
    """Tests for customer.subscription.deleted events."""

    @patch("doubleday.api.stripe_events.handler.stripe")
    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_cancels_entitlement(self, mock_dynamodb, mock_stripe, lambda_context):
        """Subscription deletion sets status to canceled."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "abc-123"},
        }

        event = _eventbridge_event(
            "customer.subscription.deleted",
            {"customer": "cus_test"},
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        mock_table.update_item.assert_called_once()
        update_args = mock_table.update_item.call_args[1]
        assert update_args["ExpressionAttributeValues"][":status"] == "canceled"


class TestPaymentFailed:
    """Tests for invoice.payment_failed events."""

    @patch("doubleday.api.stripe_events.handler.stripe")
    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_sets_past_due(self, mock_dynamodb, mock_stripe, lambda_context):
        """Payment failure sets status to past_due."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_stripe.Customer.retrieve.return_value = {
            "metadata": {"cognito_sub": "abc-123"},
        }

        event = _eventbridge_event(
            "invoice.payment_failed",
            {"customer": "cus_test"},
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        mock_table.update_item.assert_called_once()
        update_args = mock_table.update_item.call_args[1]
        assert update_args["ExpressionAttributeValues"][":status"] == "past_due"


class TestUnhandledEvent:
    """Tests for unhandled event types."""

    @patch("doubleday.api.stripe_events.handler.dynamodb")
    def test_unhandled_event_returns_processed(self, mock_dynamodb, lambda_context):
        """Unhandled event types still return processed."""
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        event = _eventbridge_event(
            "some.other.event",
            {"id": "obj_test"},
        )

        result = handler(event, lambda_context)

        assert result["processed"] is True
        assert result["event_type"] == "some.other.event"
        mock_table.put_item.assert_not_called()
        mock_table.update_item.assert_not_called()
