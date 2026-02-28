"""Unit tests for the query_neighbors API query (doubleday.api.query_neighbors.query).

The query_neighbors module queries the DynamoDB serving table by pitcher+season
and returns a QueryResult dataclass with typed shape-similarity neighbor data.

These tests mock the DynamoDB Table resource and verify: PK/SK construction,
DynamoDB Decimal-to-native coercion, empty result handling, and internal key
stripping.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from doubleday.api.query_neighbors.query import QueryResult, query_neighbors


class TestQueryNeighbors:
    """Tests for the query_neighbors function.

    Mocks a DynamoDB Table resource to simulate query responses without making
    real AWS calls.
    """

    def test_returns_query_result_with_neighbors(self):
        """Basic query returns QueryResult with typed neighbor data."""
        table = MagicMock()
        table.query.return_value = {
            "Items": [
                {
                    "PK": "PITCHER#669302#SEASON#2024",
                    "SK": "NEIGHBOR#001",
                    "entity_type": "neighbor",
                    "neighbor_pitcher": Decimal("605151"),
                    "neighbor_season": Decimal("2024"),
                    "similarity_score": Decimal("0.95"),
                    "rank": Decimal("1"),
                },
                {
                    "PK": "PITCHER#669302#SEASON#2024",
                    "SK": "NEIGHBOR#002",
                    "entity_type": "neighbor",
                    "neighbor_pitcher": Decimal("543210"),
                    "neighbor_season": Decimal("2023"),
                    "similarity_score": Decimal("0.87"),
                    "rank": Decimal("2"),
                },
            ]
        }

        result = query_neighbors(table, 669302, 2024)

        assert isinstance(result, QueryResult)
        assert result.pitcher == 669302
        assert result.season == 2024
        assert len(result.neighbors) == 2
        assert result.neighbors[0]["neighbor_pitcher"] == 605151
        assert result.neighbors[0]["similarity_score"] == 0.95
        assert result.neighbors[0]["rank"] == 1
        assert result.neighbors[1]["neighbor_pitcher"] == 543210
        assert result.neighbors[1]["neighbor_season"] == 2023
        assert "PK" not in result.neighbors[0]

    def test_queries_with_correct_pk(self):
        """Queries with correct PK and SK prefix."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        query_neighbors(table, 605151, 2024)

        call_kwargs = table.query.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":pk"] == "PITCHER#605151#SEASON#2024"
        assert call_kwargs["ExpressionAttributeValues"][":sk_prefix"] == "NEIGHBOR#"

    def test_empty_results_returns_empty_neighbors(self):
        """Empty DynamoDB result returns QueryResult with empty neighbors list."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        result = query_neighbors(table, 605151, 2024)

        assert result.neighbors == []
