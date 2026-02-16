"""Unit tests for the gold load pipeline (doubleday.pipeline.gold_load.pipeline).

The gold load rebuilds a single gold table for a given season by executing a
pair of SQL files: a DELETE (clear the season partition) followed by an INSERT
(rebuild from silver). It is parameterized by table_name so the same Lambda
serves all gold tables.

These tests mock the Athena client and verify: SQL file loading, the
DELETE-then-INSERT execution order, season parameter formatting, execution ID
tracking, and error propagation when queries fail.
"""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.pipeline.gold_load.pipeline import (
    LoadResult,
    load_sql,
    load_table,
)


class TestLoadSql:
    """Tests for load_sql — reads a SQL template file from a directory."""

    def test_reads_file_from_directory(self, tmp_path):
        """Reads the contents of a SQL file."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1")

        assert load_sql(tmp_path, "test.sql") == "SELECT 1"


class TestLoadTable:
    """Tests for load_table — the main gold load entry point.

    Uses tmp_path to create minimal DELETE/INSERT SQL templates and mocks
    run_query / get_query_row_count to simulate Athena responses.
    """

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create minimal gold SQL files for testing."""
        (tmp_path / "gold_test_delete.sql").write_text(
            "DELETE FROM gold_test WHERE season = {season}"
        )
        (tmp_path / "gold_test_insert.sql").write_text(
            "INSERT INTO gold_test SELECT * FROM silver WHERE season = {season}"
        )
        return tmp_path

    @patch("doubleday.pipeline.gold_load.pipeline.get_query_row_count")
    @patch("doubleday.pipeline.gold_load.pipeline.run_query")
    def test_runs_delete_then_insert(self, mock_run, mock_count, sql_dir):
        """Pipeline executes DELETE then INSERT and returns a LoadResult."""
        mock_run.side_effect = ["exec-1", "exec-2"]
        mock_count.return_value = 500
        client = MagicMock()

        result = load_table(client, "my_db", "bucket", sql_dir, "gold_test", 2025)

        assert isinstance(result, LoadResult)
        assert result.records_inserted == 500
        assert mock_run.call_count == 2

        sql_calls = [call.args[1] for call in mock_run.call_args_list]
        assert "DELETE" in sql_calls[0]
        assert "season = 2025" in sql_calls[0]
        assert "INSERT" in sql_calls[1]
        assert "season = 2025" in sql_calls[1]

    @patch("doubleday.pipeline.gold_load.pipeline.get_query_row_count")
    @patch("doubleday.pipeline.gold_load.pipeline.run_query")
    def test_results_dict_contains_execution_ids(self, mock_run, mock_count, sql_dir):
        """The results dict maps step names to execution IDs."""
        mock_run.side_effect = ["exec-1", "exec-2"]
        mock_count.return_value = 100
        client = MagicMock()

        result = load_table(client, "my_db", "bucket", sql_dir, "gold_test", 2025)

        assert result.results["delete_partition"] == "exec-1"
        assert result.results["insert_partition"] == "exec-2"

    @patch("doubleday.pipeline.gold_load.pipeline.run_query")
    def test_delete_failure_prevents_insert(self, mock_run, sql_dir):
        """If the DELETE query fails, the INSERT never runs."""
        mock_run.side_effect = RuntimeError("Query FAILED: access denied")
        client = MagicMock()

        with pytest.raises(RuntimeError, match="access denied"):
            load_table(client, "my_db", "bucket", sql_dir, "gold_test", 2025)

        assert mock_run.call_count == 1

    def test_missing_sql_file_raises(self, tmp_path):
        """Missing SQL file raises FileNotFoundError."""
        client = MagicMock()

        with pytest.raises(FileNotFoundError):
            load_table(client, "my_db", "bucket", tmp_path, "nonexistent", 2025)
