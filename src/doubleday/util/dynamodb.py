"""DynamoDB query utilities for the serving table."""

from decimal import Decimal

from aws_lambda_powertools import Logger

logger = Logger(child=True)


def _decimal_to_native(obj: Decimal | str) -> int | float | str:
    """Convert a Decimal value to int or float for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    return obj


def coerce_item(item: dict) -> dict:
    """Convert a DynamoDB item to a dict with native Python types.

    Strips internal keys (PK, SK, entity_type) and converts Decimal
    values to int or float.

    Args:
        item: Raw DynamoDB item dict.

    Returns:
        Cleaned dict with native Python types.
    """
    return {k: _decimal_to_native(v) for k, v in item.items() if k not in ("PK", "SK", "entity_type")}


def query_items(
    table,
    pk: str,
    sk_prefix: str,
    sk_exact: str | None = None,
) -> list[dict]:
    """Query the DynamoDB serving table by PK and SK condition.

    Args:
        table: Boto3 DynamoDB Table resource.
        pk: Partition key value.
        sk_prefix: Sort key prefix for ``begins_with`` condition.
        sk_exact: If provided, use exact SK match instead of prefix.

    Returns:
        List of items as dicts with native Python types.
    """
    if sk_exact:
        kwargs: dict = {
            "KeyConditionExpression": "PK = :pk AND SK = :sk",
            "ExpressionAttributeValues": {":pk": pk, ":sk": sk_exact},
        }
    else:
        kwargs = {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "ExpressionAttributeValues": {":pk": pk, ":sk_prefix": sk_prefix},
        }

    items = []
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return [coerce_item(item) for item in items]
