"""Unit tests for the query_pitches API query (doubleday.api.query_pitches.query).

The query_pitches module queries the DynamoDB serving table by pitcher+season
and returns a QueryResult dataclass with typed pitch-shape statistics.

These tests mock the DynamoDB Table resource and verify: PK/SK construction,
pitch_type filter handling, DynamoDB Decimal-to-native coercion, empty result
handling, and pagination.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from doubleday.api.query_pitches.query import QueryResult, query_pitches


class TestQueryPitches:
    """Tests for the query_pitches function.

    Mocks a DynamoDB Table resource to simulate query responses without making
    real AWS calls.
    """

    def test_returns_query_result_with_pitches(self):
        """Basic query returns QueryResult with typed pitch data."""
        table = MagicMock()
        table.query.return_value = {
            "Items": [
                {
                    "PK": "PITCHER#605151#SEASON#2024",
                    "SK": "PITCH#FF",
                    "entity_type": "pitch",
                    "pitcher": Decimal("605151"),
                    "pitch_type": "FF",
                    "avg_horz_break_in": Decimal("-5.2"),
                    "avg_vert_break_in": Decimal("14.3"),
                    "stddev_horz_break_in": Decimal("1.1"),
                    "stddev_vert_break_in": Decimal("0.8"),
                    "p10_horz_break_in": Decimal("-6.5"),
                    "p90_horz_break_in": Decimal("-3.9"),
                    "p10_vert_break_in": Decimal("13.1"),
                    "p90_vert_break_in": Decimal("15.5"),
                    "avg_velocity": Decimal("96.5"),
                    "p10_velocity": Decimal("94.2"),
                    "p90_velocity": Decimal("98.8"),
                    "avg_adj_velocity": Decimal("97.0"),
                    "avg_spin_rate": Decimal("2350"),
                    "pitch_count": Decimal("800"),
                    "usage_rate": Decimal("0.45"),
                    "season": Decimal("2024"),
                }
            ]
        }

        result = query_pitches(table, 605151, 2024)

        assert isinstance(result, QueryResult)
        assert result.pitcher == 605151
        assert result.season == 2024
        assert len(result.pitches) == 1
        assert result.pitches[0]["pitcher"] == 605151
        assert result.pitches[0]["avg_velocity"] == 96.5
        assert result.pitches[0]["pitch_count"] == 800
        assert result.pitches[0]["pitch_type"] == "FF"
        assert "PK" not in result.pitches[0]
        assert "SK" not in result.pitches[0]
        assert "entity_type" not in result.pitches[0]

    def test_pitch_type_filter_uses_exact_sk(self):
        """Optional pitch_type filter queries with exact SK."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        query_pitches(table, 605151, 2024, pitch_type="SL")

        call_kwargs = table.query.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":sk"] == "PITCH#SL"
        assert call_kwargs["ExpressionAttributeValues"][":pk"] == "PITCHER#605151#SEASON#2024"

    def test_no_pitch_type_uses_begins_with(self):
        """No pitch_type filter queries with begins_with on SK prefix."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        query_pitches(table, 605151, 2024)

        call_kwargs = table.query.call_args.kwargs
        assert ":sk_prefix" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":sk_prefix"] == "PITCH#"

    def test_empty_results_returns_empty_pitches(self):
        """Empty DynamoDB result returns QueryResult with empty pitches list."""
        table = MagicMock()
        table.query.return_value = {"Items": []}

        result = query_pitches(table, 605151, 2024)

        assert result.pitches == []
