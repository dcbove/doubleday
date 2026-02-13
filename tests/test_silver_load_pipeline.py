"""Unit tests for doubleday.lambdas.silver_load.pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.lambdas.silver_load.pipeline import (
    LoadResult,
    load_partition,
    load_sql,
    parse_partition_name,
)


class TestParsePartitionName:
    """Tests for parse_partition_name."""

    def test_valid_partition(self):
        """Standard partition string is parsed correctly."""
        season, game_date = parse_partition_name("season=2025/game_date=2025-03-27")
        assert season == 2025
        assert game_date == "2025-03-27"

    def test_different_year(self):
        """Different year parses correctly."""
        season, game_date = parse_partition_name("season=2024/game_date=2024-11-01")
        assert season == 2024
        assert game_date == "2024-11-01"

    def test_invalid_format_raises(self):
        """Malformed partition string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid partition_name"):
            parse_partition_name("bad-format")

    def test_missing_game_date_raises(self):
        """Partition with only season raises ValueError."""
        with pytest.raises(ValueError, match="Invalid partition_name"):
            parse_partition_name("season=2025")

    def test_missing_season_raises(self):
        """Partition with only game_date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid partition_name"):
            parse_partition_name("game_date=2025-03-27")


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
            "silver_clear_partition_from_staging_table.sql": (
                "DELETE WHERE season={season}"
            ),
            "silver_load_partition_into_staging_table.sql": (
                "INSERT season={season} game_date='{game_date}'"
            ),
            "silver_validate_staging_table.sql": (
                "SELECT COUNT(*) WHERE season={season}"
            ),
            "silver_merge_partition_into_canonical_table.sql": (
                "MERGE season={season}"
            ),
        }
        for name, content in templates.items():
            (tmp_path / name).write_text(content)
        return tmp_path

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_runs_all_steps_in_order(self, mock_run, mock_count, sql_dir):
        """Pipeline executes all five steps and returns a LoadResult."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4", "exec-5"]
        # load_partition returns 100, validate returns 0, merge returns 100
        mock_count.side_effect = [100, 0, 100]
        client = MagicMock()

        result = load_partition(client, "my_db", "bucket", sql_dir, 2025, "2025-03-27")

        assert isinstance(result, LoadResult)
        assert result.records_loaded == 100
        assert result.records_merged == 100
        assert mock_run.call_count == 5

        # Verify step order from the SQL passed to run_query
        sql_calls = [call.args[1] for call in mock_run.call_args_list]
        assert "DELETE" in sql_calls[0]
        assert "INSERT" in sql_calls[1]
        assert "SELECT" in sql_calls[2]
        assert "MERGE" in sql_calls[3]
        assert "DELETE" in sql_calls[4]

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_formats_sql_with_partition_values(self, mock_run, mock_count, sql_dir):
        """SQL templates are formatted with season and game_date."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4", "exec-5"]
        mock_count.side_effect = [50, 0, 50]
        client = MagicMock()

        load_partition(client, "my_db", "bucket", sql_dir, 2024, "2024-03-01")

        load_sql = mock_run.call_args_list[1].args[1]
        assert "2024" in load_sql
        assert "2024-03-01" in load_sql

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_validation_failure_raises_before_merge(
        self, mock_run, mock_count, sql_dir
    ):
        """Duplicate keys in staging raises ValueError; merge never runs."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3"]
        # load_partition returns 100, validate returns 5 duplicates
        mock_count.side_effect = [100, 5]
        client = MagicMock()

        with pytest.raises(ValueError, match="5 duplicate"):
            load_partition(client, "my_db", "bucket", sql_dir, 2025, "2025-03-27")

        # Only 3 queries ran — merge and final clear never executed
        assert mock_run.call_count == 3

    @patch("doubleday.lambdas.silver_load.pipeline.get_query_row_count")
    @patch("doubleday.lambdas.silver_load.pipeline.run_query")
    def test_results_dict_contains_execution_ids(self, mock_run, mock_count, sql_dir):
        """The results dict maps step names to execution IDs."""
        mock_run.side_effect = ["exec-1", "exec-2", "exec-3", "exec-4", "exec-5"]
        mock_count.side_effect = [100, 0, 100]
        client = MagicMock()

        result = load_partition(client, "my_db", "bucket", sql_dir, 2025, "2025-03-27")

        assert result.results["clear_staging_pre"] == "exec-1"
        assert result.results["load_partition"] == "exec-2"
        assert result.results["validate_staging"] == "exec-3"
        assert result.results["merge_partition"] == "exec-4"
        assert result.results["clear_staging_post"] == "exec-5"
