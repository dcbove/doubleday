"""Unit tests for doubleday.lambdas.silver_load.pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.lambdas.silver_load.pipeline import (
    LoadResult,
    load_partition,
    load_sql,
)


class TestLoadSql:
    """Tests for load_sql."""

    def test_reads_file_from_directory(self, tmp_path):
        """Reads the contents of a SQL file."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1")

        assert load_sql(tmp_path, "test.sql") == "SELECT 1"


class TestLoadPartition:
    """Tests for load_partition."""

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create minimal SQL template files for testing."""
        templates = {
            "silver_load_partition_into_staging_table.sql": (
                "INSERT season={season} game_date='{game_date}'"
            ),
            "silver_validate_staging_table.sql": (
                "SELECT COUNT(*) WHERE season={season}"
            ),
            "silver_delete_partition_from_canonical_table.sql": (
                "DELETE WHERE season={season}"
            ),
            "silver_insert_partition_into_canonical_table.sql": (
                "INSERT INTO canonical WHERE season={season}"
            ),
        }
        for name, content in templates.items():
            (tmp_path / name).write_text(content)
        return tmp_path

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_runs_all_steps_in_order(self, mock_run, mock_count, sql_dir):
        """Pipeline executes all four steps and returns a LoadResult."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4"]
        # load returns 100, validate returns 0, insert returns 100
        mock_count.side_effect = [100, 0, 100]
        client = MagicMock()

        result = load_partition(
            client, "my_db", "bucket", sql_dir, 2025, "2025-03-27", "batch-abc"
        )

        assert isinstance(result, LoadResult)
        assert result.records_loaded == 100
        assert result.records_inserted == 100
        assert mock_run.call_count == 4

        # Verify step order from the SQL passed to run_query
        sql_calls = [call.args[1] for call in mock_run.call_args_list]
        assert "INSERT" in sql_calls[0]
        assert "SELECT" in sql_calls[1]
        assert "DELETE" in sql_calls[2]
        assert "INSERT INTO canonical" in sql_calls[3]

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_formats_sql_with_partition_values(self, mock_run, mock_count, sql_dir):
        """SQL templates are formatted with season and game_date."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4"]
        mock_count.side_effect = [50, 0, 50]
        client = MagicMock()

        load_partition(
            client, "my_db", "bucket", sql_dir, 2024, "2024-03-01", "batch-xyz"
        )

        insert_sql = mock_run.call_args_list[0].args[1]
        assert "2024" in insert_sql
        assert "2024-03-01" in insert_sql

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_validation_failure_raises_before_replace(
        self, mock_run, mock_count, sql_dir
    ):
        """Duplicate keys in staging raises ValueError; replace never runs."""
        mock_run.side_effect = ["exec-1", "exec-2"]
        # load returns 100, validate returns 5 duplicates
        mock_count.side_effect = [100, 5]
        client = MagicMock()

        with pytest.raises(ValueError, match="5 duplicate"):
            load_partition(
                client, "my_db", "bucket", sql_dir, 2025, "2025-03-27", "batch-abc"
            )

        # Only 2 queries ran — delete/insert never executed
        assert mock_run.call_count == 2

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_results_dict_contains_execution_ids(self, mock_run, mock_count, sql_dir):
        """The results dict maps step names to execution IDs."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4"]
        mock_count.side_effect = [100, 0, 100]
        client = MagicMock()

        result = load_partition(
            client, "my_db", "bucket", sql_dir, 2025, "2025-03-27", "batch-abc"
        )

        assert result.results["load_partition"] == "exec-1"
        assert result.results["validate_staging"] == "exec-2"
        assert result.results["delete_canonical"] == "exec-3"
        assert result.results["insert_canonical"] == "exec-4"
