"""Unit tests for the query_neighbors API query (doubleday.api.query_neighbors.query).

The query_neighbors module reads a SQL template, formats it with pitcher ID and
season, executes it against Athena, and returns a QueryResult dataclass with
typed shape-similarity neighbor data (neighbor pitcher, season, score, rank).

These tests mock the Athena client and verify: SQL template loading and
formatting, Athena string-to-Python type coercion, empty result handling,
and error propagation.
"""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.api.query_neighbors.query import QueryResult, query_neighbors


class TestQueryNeighbors:
    """Tests for the query_neighbors function.

    Uses a tmp_path fixture to create a minimal SQL template on disk, and mocks
    run_query / get_query_results to simulate Athena responses without making
    real AWS calls.
    """

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create minimal SQL template for testing."""
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "query_neighbors.sql").write_text(
            "SELECT * FROM gold_repertoire_shape_neighbors"
            " WHERE source_pitcher = {pitcher} AND source_season = {season}"
        )
        return tmp_path

    @patch("doubleday.api.query_neighbors.query.get_query_results")
    @patch("doubleday.api.query_neighbors.query.run_query")
    def test_returns_query_result_with_neighbors(self, mock_run, mock_results, sql_dir):
        """Basic query returns QueryResult with typed neighbor data."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "neighbor_pitcher": "605151",
                "neighbor_season": "2024",
                "similarity_score": "0.95",
                "rank": "1",
            },
            {
                "neighbor_pitcher": "543210",
                "neighbor_season": "2023",
                "similarity_score": "0.87",
                "rank": "2",
            },
        ]
        client = MagicMock()

        result = query_neighbors(client, "my_db", "bucket", sql_dir, 669302, 2024)

        assert isinstance(result, QueryResult)
        assert result.pitcher == 669302
        assert result.season == 2024
        assert len(result.neighbors) == 2
        assert result.neighbors[0]["neighbor_pitcher"] == 605151
        assert result.neighbors[0]["similarity_score"] == 0.95
        assert result.neighbors[0]["rank"] == 1
        assert result.neighbors[1]["neighbor_pitcher"] == 543210
        assert result.neighbors[1]["neighbor_season"] == 2023

    @patch("doubleday.api.query_neighbors.query.get_query_results")
    @patch("doubleday.api.query_neighbors.query.run_query")
    def test_empty_results_returns_empty_neighbors(self, mock_run, mock_results, sql_dir):
        """Empty Athena result returns QueryResult with empty neighbors list."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = []
        client = MagicMock()

        result = query_neighbors(client, "my_db", "bucket", sql_dir, 605151, 2024)

        assert result.neighbors == []

    @patch("doubleday.api.query_neighbors.query.run_query")
    def test_athena_failure_propagates(self, mock_run, sql_dir):
        """Athena query failure propagates RuntimeError."""
        mock_run.side_effect = RuntimeError("Query FAILED: access denied")
        client = MagicMock()

        with pytest.raises(RuntimeError, match="access denied"):
            query_neighbors(client, "my_db", "bucket", sql_dir, 605151, 2024)
