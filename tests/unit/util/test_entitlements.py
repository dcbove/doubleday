"""Unit tests for the entitlements utility (doubleday.util.entitlements).

Tests the check_subscription and is_active functions that data endpoints use
to verify whether a user has an active subscription before serving data.
"""

from unittest.mock import MagicMock

from doubleday.util.entitlements import check_subscription, is_active


class TestCheckSubscription:
    """Tests for check_subscription DynamoDB lookup."""

    def test_returns_item_when_found(self):
        """Returns the entitlement item when the user exists."""
        table = MagicMock()
        table.get_item.return_value = {
            "Item": {"PK": "USER#sub-123", "status": "active", "tier": "basic"},
        }

        result = check_subscription(table, "sub-123")

        assert result["status"] == "active"
        table.get_item.assert_called_once_with(Key={"PK": "USER#sub-123"})

    def test_returns_none_when_not_found(self):
        """Returns None when the user has no entitlement record."""
        table = MagicMock()
        table.get_item.return_value = {}

        result = check_subscription(table, "sub-missing")

        assert result is None


class TestIsActive:
    """Tests for is_active status check."""

    def test_active_status_returns_true(self):
        """Active subscription returns True."""
        assert is_active({"status": "active"}) is True

    def test_inactive_status_returns_false(self):
        """Inactive subscription returns False."""
        assert is_active({"status": "inactive"}) is False

    def test_canceled_status_returns_false(self):
        """Canceled subscription returns False."""
        assert is_active({"status": "canceled"}) is False

    def test_past_due_status_returns_false(self):
        """Past due subscription returns False."""
        assert is_active({"status": "past_due"}) is False

    def test_none_entitlement_returns_false(self):
        """None entitlement returns False."""
        assert is_active(None) is False

    def test_missing_status_returns_false(self):
        """Entitlement with no status field returns False."""
        assert is_active({"tier": "basic"}) is False
