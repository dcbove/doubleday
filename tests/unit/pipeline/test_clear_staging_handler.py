"""Unit tests for the clear staging handler (doubleday.pipeline.clear_staging.handler).

The clear_staging Lambda runs after all silver loads complete in a Step Function
execution. It reads a SQL template, formats it with the batch_id (a UUID that
tags all staging rows from one pipeline run), and executes it against Athena to
bulk-delete those rows from the silver_pitches_staging table.

These tests mock the Athena client, SQL file reads, and Powertools metrics to
verify the handler loads the correct SQL template, formats it with the batch_id,
and returns the Athena execution ID. Environment variables are set before import
because the handler reads them at module level.
"""

import json
import os
from unittest.mock import MagicMock, patch

# Set env vars before importing handler (module-level os.environ reads)
os.environ.setdefault("GLUE_DATABASE", "test_db")
os.environ.setdefault("ATHENA_OUTPUT_BUCKET", "test-bucket")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.pipeline.clear_staging.handler import handler  # noqa: E402


class TestClearStagingHandler:
    """Tests for the clear_staging handler.

    Mocks are extensive here because the handler has module-level state:
    an Athena client, Powertools metrics, and constants read from environment
    variables and the filesystem.
    """

    @patch("doubleday.pipeline.clear_staging.handler.SQL_DIR")
    @patch("doubleday.pipeline.clear_staging.handler.run_query")
    @patch("doubleday.pipeline.clear_staging.handler.metrics")
    @patch("doubleday.pipeline.clear_staging.handler.athena")
    @patch("doubleday.pipeline.clear_staging.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.clear_staging.handler.OUTPUT_BUCKET", "test-bucket")
    def test_clears_staging_with_batch_id(
        self, mock_athena, mock_metrics, mock_run, mock_sql_dir
    ):
        """Handler formats SQL with batch_id and calls run_query."""
        mock_sql_file = MagicMock()
        mock_sql_file.read_text.return_value = (
            "DELETE FROM silver_pitches_staging" " WHERE batch_id = '{batch_id}'\n"
        )
        mock_sql_dir.__truediv__ = MagicMock(return_value=mock_sql_file)
        mock_run.return_value = "exec-123"

        result = handler({"batch_id": "abc-def-123"}, None)

        mock_run.assert_called_once_with(
            mock_athena,
            "DELETE FROM silver_pitches_staging" " WHERE batch_id = 'abc-def-123'\n",
            "test_db",
            "test-bucket",
        )
        body = json.loads(result["body"])
        assert result["statusCode"] == 200
        assert body["batch_id"] == "abc-def-123"
        assert body["execution_id"] == "exec-123"

    @patch("doubleday.pipeline.clear_staging.handler.SQL_DIR")
    @patch("doubleday.pipeline.clear_staging.handler.run_query")
    @patch("doubleday.pipeline.clear_staging.handler.metrics")
    @patch("doubleday.pipeline.clear_staging.handler.athena")
    @patch("doubleday.pipeline.clear_staging.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.clear_staging.handler.OUTPUT_BUCKET", "test-bucket")
    def test_reads_correct_sql_file(
        self, mock_athena, mock_metrics, mock_run, mock_sql_dir
    ):
        """Handler reads the clear partition SQL template."""
        mock_sql_file = MagicMock()
        mock_sql_file.read_text.return_value = "DELETE WHERE batch_id = '{batch_id}'"
        mock_sql_dir.__truediv__ = MagicMock(return_value=mock_sql_file)
        mock_run.return_value = "exec-456"

        handler({"batch_id": "test-batch"}, None)

        mock_sql_dir.__truediv__.assert_called_once_with(
            "silver_clear_partition_from_staging_table.sql"
        )
