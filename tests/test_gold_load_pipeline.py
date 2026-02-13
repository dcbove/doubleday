"""Unit tests for doubleday.lambdas.gold_load.pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doubleday.lambdas.gold_load.pipeline import (
    LoadResult,
    load_sql,
    load_table,
    split_statements,
)


class TestLoadSql:
    """Tests for load_sql."""

    def test_reads_file_from_directory(self, tmp_path):
        """Reads the contents of a SQL file."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1")

        assert load_sql(tmp_path, "test.sql") == "SELECT 1"


class TestSplitStatements:
    """Tests for split_statements."""

    def test_splits_on_semicolons(self):
        """Splits SQL into individual statements."""
        sql = "DELETE FROM t WHERE x = 1;\nINSERT INTO t SELECT 1;"
        result = split_statements(sql)
        assert len(result) == 2
        assert "DELETE" in result[0]
        assert "INSERT" in result[1]

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace from statements."""
        sql = "  DELETE FROM t;  \n  INSERT INTO t SELECT 1;  "
        result = split_statements(sql)
        assert result[0] == "DELETE FROM t"
        assert result[1] == "INSERT INTO t SELECT 1"

    def test_skips_empty_fragments(self):
        """Ignores empty fragments from trailing semicolons."""
        sql = "DELETE FROM t;\n"
        result = split_statements(sql)
        assert len(result) == 1

    def test_skips_comment_only_fragments(self):
        """Ignores fragments that are only comments."""
        sql = "-- Step 1: delete\nDELETE FROM t;\n-- Step 2: insert\nINSERT INTO t SELECT 1;"
        result = split_statements(sql)
        assert len(result) == 2
        assert "DELETE" in result[0]
        assert "INSERT" in result[1]


class TestLoadTable:
    """Tests for load_table."""

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create a minimal gold SQL file for testing."""
        sql = (
            "-- Step 1\n"
            "DELETE FROM gold_test WHERE season = {season};\n"
            "-- Step 2\n"
            "INSERT INTO gold_test SELECT * FROM silver WHERE season = {season};"
        )
        (tmp_path / "gold_test.sql").write_text(sql)
        return tmp_path

    @patch("doubleday.lambdas.gold_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.gold_load.pipeline.run_query")
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

    @patch("doubleday.lambdas.gold_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.gold_load.pipeline.run_query")
    def test_results_dict_contains_execution_ids(self, mock_run, mock_count, sql_dir):
        """The results dict maps step names to execution IDs."""
        mock_run.side_effect = ["exec-1", "exec-2"]
        mock_count.return_value = 100
        client = MagicMock()

        result = load_table(client, "my_db", "bucket", sql_dir, "gold_test", 2025)

        assert result.results["delete_partition"] == "exec-1"
        assert result.results["insert_partition"] == "exec-2"

    @patch("doubleday.lambdas.gold_load.pipeline.run_query")
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
