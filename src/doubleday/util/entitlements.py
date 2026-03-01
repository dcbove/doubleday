"""Entitlements check utility for API endpoints."""

from typing import Any

from aws_lambda_powertools import Logger

logger = Logger(child=True)


def check_subscription(table: Any, cognito_sub: str) -> dict | None:
    """Look up a user's subscription entitlement.

    Args:
        table: Boto3 DynamoDB Table resource for entitlements.
        cognito_sub: The user's Cognito sub claim.

    Returns:
        The entitlement item dict if found, None otherwise.
    """
    response = table.get_item(Key={"PK": f"USER#{cognito_sub}"})
    item: dict[str, Any] | None = response.get("Item")
    return item


def is_active(entitlement: dict | None) -> bool:
    """Check if an entitlement has an active subscription.

    Args:
        entitlement: The entitlement item from DynamoDB, or None.

    Returns:
        True if the user has an active subscription.
    """
    if not entitlement:
        return False
    return entitlement.get("status") == "active"
