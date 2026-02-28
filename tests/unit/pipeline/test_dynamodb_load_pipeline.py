"""Unit tests for the DynamoDB load pipeline (doubleday.pipeline.dynamodb_load.pipeline).

The DynamoDB load reads gold Iceberg table data via Athena and batch-writes
items to a DynamoDB serving table. It handles both pitches and neighbors
entity types.

These tests mock the Athena client and DynamoDB Table resource to verify:
query execution, item construction (PK/SK format, type coercion), batch
writing, deletion of stale items, and error propagation.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from doubleday.pipeline.dynamodb_load.pipeline import (
    DynamoDBLoadResult,
    load_to_dynamodb,
)


class TestLoadToDynamoDB:
    """Tests for load_to_dynamodb."""

    @pytest.fixture()
    def sql_dir(self, tmp_path):
        """Create minimal SQL templates for testing."""
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir()
        (pipeline_dir / "dynamodb_load_pitches.sql").write_text(
            "SELECT * FROM gold_pitches_shape_season WHERE season = {season}"
        )
        (pipeline_dir / "dynamodb_load_neighbors.sql").write_text(
            "SELECT * FROM gold_repertoire_shape_neighbors WHERE source_season = {season}"
        )
        return tmp_path

    @pytest.fixture()
    def mock_table(self):
        """Create a mock DynamoDB Table with batch_writer context manager."""
        table = MagicMock()
        table.scan.return_value = {"Items": []}
        batch_writer = MagicMock()
        table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_writer)
        table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
        return table

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_loads_pitches_with_correct_pk_sk(self, mock_run, mock_results, sql_dir, mock_table):
        """Pitches load builds correct PK/SK and coerces numeric columns."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "pitcher": "605151",
                "pitch_type": "FF",
                "avg_velocity": "96.5",
                "pitch_count": "800",
                "season": "2025",
            }
        ]

        result = load_to_dynamodb(MagicMock(), mock_table, "db", "bucket", sql_dir, "pitches", 2025)

        assert isinstance(result, DynamoDBLoadResult)
        assert result.records_loaded == 1
        assert result.records_deleted == 0

        batch = mock_table.batch_writer.return_value.__enter__.return_value
        put_call = batch.put_item.call_args
        item = put_call.kwargs["Item"]
        assert item["PK"] == "PITCHER#605151#SEASON#2025"
        assert item["SK"] == "PITCH#FF"
        assert item["entity_type"] == "pitch"
        assert item["avg_velocity"] == Decimal("96.5")
        assert item["pitcher"] == Decimal("605151")

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_loads_neighbors_with_zero_padded_rank(self, mock_run, mock_results, sql_dir, mock_table):
        """Neighbors load builds zero-padded rank SK."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "source_pitcher": "669302",
                "source_season": "2025",
                "neighbor_pitcher": "605151",
                "neighbor_season": "2024",
                "similarity_score": "0.95",
                "rank": "1",
            }
        ]

        result = load_to_dynamodb(MagicMock(), mock_table, "db", "bucket", sql_dir, "neighbors", 2025)

        assert result.records_loaded == 1

        batch = mock_table.batch_writer.return_value.__enter__.return_value
        item = batch.put_item.call_args.kwargs["Item"]
        assert item["PK"] == "PITCHER#669302#SEASON#2025"
        assert item["SK"] == "NEIGHBOR#001"
        assert item["entity_type"] == "neighbor"
        assert item["similarity_score"] == Decimal("0.95")

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_deletes_existing_items_before_loading(self, mock_run, mock_results, sql_dir):
        """Existing items for the entity/season are deleted before loading."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = []

        table = MagicMock()
        table.scan.return_value = {
            "Items": [
                {"PK": "PITCHER#1#SEASON#2025", "SK": "PITCH#FF"},
                {"PK": "PITCHER#1#SEASON#2025", "SK": "PITCH#SL"},
            ]
        }
        delete_batch = MagicMock()
        table.batch_writer.return_value.__enter__ = MagicMock(return_value=delete_batch)
        table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        result = load_to_dynamodb(MagicMock(), table, "db", "bucket", sql_dir, "pitches", 2025)

        assert result.records_deleted == 2
        assert delete_batch.delete_item.call_count == 2

    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_athena_failure_propagates(self, mock_run, sql_dir):
        """Athena query failure propagates RuntimeError."""
        mock_run.side_effect = RuntimeError("Query FAILED: access denied")

        with pytest.raises(RuntimeError, match="access denied"):
            load_to_dynamodb(MagicMock(), MagicMock(), "db", "bucket", sql_dir, "pitches", 2025)

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_empty_string_numeric_column_omitted(self, mock_run, mock_results, sql_dir, mock_table):
        """Empty string in a numeric column is omitted from the DynamoDB item."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "pitcher": "605151",
                "pitch_type": "FF",
                "avg_velocity": "",
                "pitch_count": "100",
                "season": "2025",
            }
        ]

        load_to_dynamodb(MagicMock(), mock_table, "db", "bucket", sql_dir, "pitches", 2025)

        batch = mock_table.batch_writer.return_value.__enter__.return_value
        item = batch.put_item.call_args.kwargs["Item"]
        assert "avg_velocity" not in item
        assert item["pitch_count"] == Decimal("100")

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_null_string_column_omitted(self, mock_run, mock_results, sql_dir, mock_table):
        """Null/empty string values are omitted from the DynamoDB item."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {
                "pitcher": "605151",
                "pitch_type": "",
                "avg_velocity": "96.5",
                "pitch_count": "100",
                "season": "2025",
            }
        ]

        load_to_dynamodb(MagicMock(), mock_table, "db", "bucket", sql_dir, "pitches", 2025)

        batch = mock_table.batch_writer.return_value.__enter__.return_value
        item = batch.put_item.call_args.kwargs["Item"]
        assert "pitch_type" not in item

    @patch("doubleday.pipeline.dynamodb_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dynamodb_load.pipeline.run_query")
    def test_formats_season_into_sql(self, mock_run, mock_results, sql_dir, mock_table):
        """Season parameter is formatted into the SQL template."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = []

        load_to_dynamodb(MagicMock(), mock_table, "db", "bucket", sql_dir, "pitches", 2025)

        sql_arg = mock_run.call_args.args[1]
        assert "season = 2025" in sql_arg
