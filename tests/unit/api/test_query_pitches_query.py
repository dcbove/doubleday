"""Unit tests for the query_pitches API query (doubleday.api.query_pitches.query).

The query_pitches module reads a SQL template, formats it with pitcher ID and
season, executes it against Athena, and returns a QueryResult dataclass with
typed pitch-shape statistics (movement, velocity, spin, usage).

These tests mock the Athena client and verify: SQL template loading and
formatting, pitch_type filter appending, Athena string-to-Python type coercion,
empty result handling, and error propagation.
"""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.api.query_pitches.query import QueryResult, query_pitches


class TestQueryPitches:
    """Tests for the query_pitches function.

    Uses a tmp_path fixture to create a minimal SQL template on disk, and mocks
    run_query / get_query_results to simulate Athena responses without making
    real AWS calls.
    """

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create minimal SQL template for testing."""
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "query_pitches.sql").write_text(
            "SELECT * FROM gold_pitches_shape_season" " WHERE pitcher = {pitcher} AND season = {season}"
        )
        return tmp_path

    @patch("doubleday.api.query_pitches.query.get_query_results")
    @patch("doubleday.api.query_pitches.query.run_query")
    def test_returns_query_result_with_pitches(self, mock_run, mock_results, sql_dir):
        """Basic query returns QueryResult with typed pitch data."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "pitcher": "605151",
                "pitch_type": "FF",
                "avg_horz_break_in": "-5.2",
                "avg_vert_break_in": "14.3",
                "stddev_horz_break_in": "1.1",
                "stddev_vert_break_in": "0.8",
                "p10_horz_break_in": "-6.5",
                "p90_horz_break_in": "-3.9",
                "p10_vert_break_in": "13.1",
                "p90_vert_break_in": "15.5",
                "avg_velocity": "96.5",
                "p10_velocity": "94.2",
                "p90_velocity": "98.8",
                "avg_adj_velocity": "97.0",
                "avg_spin_rate": "2350.0",
                "pitch_count": "800",
                "usage_rate": "0.45",
                "season": "2024",
            }
        ]
        client = MagicMock()

        result = query_pitches(client, "my_db", "bucket", sql_dir, 605151, 2024)

        assert isinstance(result, QueryResult)
        assert result.pitcher == 605151
        assert result.season == 2024
        assert len(result.pitches) == 1
        assert result.pitches[0]["pitcher"] == 605151
        assert result.pitches[0]["avg_velocity"] == 96.5
        assert result.pitches[0]["pitch_count"] == 800
        assert result.pitches[0]["pitch_type"] == "FF"

    @patch("doubleday.api.query_pitches.query.get_query_results")
    @patch("doubleday.api.query_pitches.query.run_query")
    def test_pitch_type_filter_appends_where_clause(self, mock_run, mock_results, sql_dir):
        """Optional pitch_type filter adds AND clause to SQL."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = []
        client = MagicMock()

        query_pitches(client, "my_db", "bucket", sql_dir, 605151, 2024, pitch_type="SL")

        sql_arg = mock_run.call_args.args[1]
        assert "pitch_type = 'SL'" in sql_arg

    @patch("doubleday.api.query_pitches.query.get_query_results")
    @patch("doubleday.api.query_pitches.query.run_query")
    def test_empty_results_returns_empty_pitches(self, mock_run, mock_results, sql_dir):
        """Empty Athena result returns QueryResult with empty pitches list."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = []
        client = MagicMock()

        result = query_pitches(client, "my_db", "bucket", sql_dir, 605151, 2024)

        assert result.pitches == []

    @patch("doubleday.api.query_pitches.query.run_query")
    def test_athena_failure_propagates(self, mock_run, sql_dir):
        """Athena query failure propagates RuntimeError."""
        mock_run.side_effect = RuntimeError("Query FAILED: access denied")
        client = MagicMock()

        with pytest.raises(RuntimeError, match="access denied"):
            query_pitches(client, "my_db", "bucket", sql_dir, 605151, 2024)
