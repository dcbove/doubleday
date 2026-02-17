"""Unit tests for the silver load handler (doubleday.pipeline.silver_load.handler).

The silver_load Lambda processes a single game_date partition through the silver
load pipeline. On success it emits RecordsLoaded/RecordsInserted/PartitionsInserted
metrics. On failure it writes a JSON failure record to S3, logs an error, emits a
SilverLoadFailed metric, and re-raises the exception so the Step Function Catch
can handle it.

Environment variables are set before import because the handler reads them at
module level.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before importing handler (module-level os.environ reads)
os.environ.setdefault("GLUE_DATABASE", "test_db")
os.environ.setdefault("ATHENA_OUTPUT_BUCKET", "test-bucket")
os.environ.setdefault("LAKEHOUSE_BUCKET", "test-lakehouse")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.pipeline.silver_load.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context for Powertools inject_lambda_context."""
    ctx = MagicMock()
    ctx.function_name = "test-silver-load"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


@pytest.fixture()
def silver_event():
    """Create a standard silver load event."""
    return {
        "season": 2024,
        "game_date": "2024-03-01",
        "batch_id": "batch-abc-123",
    }


class TestSilverLoadHandlerSuccess:
    """Tests for the silver_load handler success path."""

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_success_returns_200(
        self,
        mock_athena,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """Handler returns 200 with partition results on success."""
        mock_load.return_value = MagicMock(
            records_loaded=100,
            records_inserted=95,
            results={"load_partition": "exec-1", "insert_canonical": "exec-2"},
        )

        result = handler(silver_event, lambda_context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["season"] == 2024
        assert body["game_date"] == "2024-03-01"
        assert body["records_loaded"] == 100
        assert body["records_inserted"] == 95

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_success_emits_metrics(
        self,
        mock_athena,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """Handler emits RecordsLoaded, RecordsInserted, and PartitionsInserted."""
        mock_load.return_value = MagicMock(
            records_loaded=50,
            records_inserted=48,
            results={},
        )

        handler(silver_event, lambda_context)

        calls = mock_metrics.add_metric.call_args_list
        metric_names = [c.kwargs["name"] for c in calls]
        assert "RecordsLoaded" in metric_names
        assert "RecordsInserted" in metric_names
        assert "PartitionsInserted" in metric_names

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_success_calls_load_partition(
        self,
        mock_athena,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """Handler calls load_partition with correct arguments."""
        mock_load.return_value = MagicMock(records_loaded=10, records_inserted=10, results={})

        handler(silver_event, lambda_context)

        mock_load.assert_called_once_with(
            mock_athena,
            "test_db",
            "test-bucket",
            mock_sql_dir,
            2024,
            "2024-03-01",
            "batch-abc-123",
        )


class TestSilverLoadHandlerFailure:
    """Tests for the silver_load handler failure path."""

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.s3")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_failure_writes_to_s3(
        self,
        mock_athena,
        mock_s3,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """On failure, handler writes a JSON failure record to S3."""
        mock_load.side_effect = ValueError("Staging validation failed")

        with pytest.raises(ValueError, match="Staging validation failed"):
            handler(silver_event, lambda_context)

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-lakehouse"
        assert call_kwargs["Key"] == "failures/silver_load/batch-abc-123/2024-03-01.json"

        record = json.loads(call_kwargs["Body"])
        assert record["batch_id"] == "batch-abc-123"
        assert record["season"] == 2024
        assert record["game_date"] == "2024-03-01"
        assert record["error_type"] == "ValueError"
        assert "Staging validation failed" in record["error_message"]
        assert "timestamp" in record

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.s3")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_failure_emits_silver_load_failed_metric(
        self,
        mock_athena,
        mock_s3,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """On failure, handler emits SilverLoadFailed metric."""
        mock_load.side_effect = RuntimeError("Athena timeout")

        with pytest.raises(RuntimeError):
            handler(silver_event, lambda_context)

        calls = mock_metrics.add_metric.call_args_list
        metric_names = [c.kwargs["name"] for c in calls]
        assert "SilverLoadFailed" in metric_names

    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.s3")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_failure_reraises_exception(
        self,
        mock_athena,
        mock_s3,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        silver_event,
        lambda_context,
    ):
        """On failure, handler re-raises the original exception."""
        original_error = ValueError("Duplicate keys found")
        mock_load.side_effect = original_error

        with pytest.raises(ValueError, match="Duplicate keys found"):
            handler(silver_event, lambda_context)

    @patch("doubleday.pipeline.silver_load.handler.logger")
    @patch("doubleday.pipeline.silver_load.handler.SQL_DIR")
    @patch("doubleday.pipeline.silver_load.handler.load_partition")
    @patch("doubleday.pipeline.silver_load.handler.metrics")
    @patch("doubleday.pipeline.silver_load.handler.s3")
    @patch("doubleday.pipeline.silver_load.handler.athena")
    @patch("doubleday.pipeline.silver_load.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    @patch("doubleday.pipeline.silver_load.handler.DATABASE", "test_db")
    @patch("doubleday.pipeline.silver_load.handler.OUTPUT_BUCKET", "test-bucket")
    def test_failure_logs_error(
        self,
        mock_athena,
        mock_s3,
        mock_metrics,
        mock_load,
        mock_sql_dir,
        mock_logger,
        silver_event,
        lambda_context,
    ):
        """On failure, handler logs an error with structured fields."""
        mock_load.side_effect = ValueError("Bad data")

        with pytest.raises(ValueError):
            handler(silver_event, lambda_context)

        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args.kwargs
        assert call_kwargs["extra"]["batch_id"] == "batch-abc-123"
        assert call_kwargs["extra"]["game_date"] == "2024-03-01"
        assert call_kwargs["extra"]["season"] == 2024
