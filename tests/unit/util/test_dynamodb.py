"""Unit tests for DynamoDB utility functions (doubleday.util.dynamodb).

The dynamodb utility provides reusable helpers for querying the DynamoDB
serving table and converting items from DynamoDB types to native Python types.

These tests verify: internal key stripping, Decimal-to-int/float coercion,
prefix and exact SK queries, and response pagination.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from doubleday.util.dynamodb import coerce_item, query_items


class TestCoerceItem:
    """Tests for coerce_item."""

    def test_strips_pk_sk_entity_type(self):
        """Internal keys are removed from the output."""
        item = {"PK": "x", "SK": "y", "entity_type": "z", "name": "test"}
        assert coerce_item(item) == {"name": "test"}

    def test_converts_whole_decimal_to_int(self):
        """Whole-number Decimals become Python ints."""
        item = {"count": Decimal("42")}
        result = coerce_item(item)
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_converts_fractional_decimal_to_float(self):
        """Fractional Decimals become Python floats."""
        item = {"score": Decimal("0.95")}
        result = coerce_item(item)
        assert result["score"] == 0.95
        assert isinstance(result["score"], float)

    def test_preserves_strings(self):
        """String values pass through unchanged."""
        item = {"pitch_type": "FF"}
        assert coerce_item(item) == {"pitch_type": "FF"}

    def test_empty_item_returns_empty(self):
        """Item with only internal keys returns empty dict."""
        item = {"PK": "x", "SK": "y", "entity_type": "z"}
        assert coerce_item(item) == {}


class TestQueryItems:
    """Tests for query_items."""

    def test_queries_with_sk_prefix(self):
        """Queries using begins_with on SK prefix."""
        table = MagicMock()
        table.query.return_value = {"Items": [{"PK": "x", "SK": "y", "entity_type": "z", "data": "val"}]}

        result = query_items(table, "PK_VAL", "SK_PREFIX")

        assert len(result) == 1
        assert result[0] == {"data": "val"}
        call_kwargs = table.query.call_args.kwargs
        assert ":sk_prefix" in call_kwargs["ExpressionAttributeValues"]

    def test_queries_with_exact_sk(self):
        """Queries using exact SK match when sk_exact is provided."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        query_items(table, "PK_VAL", "PREFIX", sk_exact="EXACT")

        call_kwargs = table.query.call_args.kwargs
        assert ":sk" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":sk"] == "EXACT"

    def test_paginates_responses(self):
        """Handles paginated DynamoDB responses."""
        table = MagicMock()
        table.query.side_effect = [
            {
                "Items": [{"PK": "x", "SK": "y1", "entity_type": "z", "a": "1"}],
                "LastEvaluatedKey": {"PK": "x", "SK": "y1"},
            },
            {
                "Items": [{"PK": "x", "SK": "y2", "entity_type": "z", "a": "2"}],
            },
        ]

        result = query_items(table, "PK_VAL", "SK_PREFIX")

        assert len(result) == 2
        assert table.query.call_count == 2

    def test_empty_response(self):
        """Empty DynamoDB response returns empty list."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        result = query_items(table, "PK_VAL", "SK_PREFIX")

        assert result == []
