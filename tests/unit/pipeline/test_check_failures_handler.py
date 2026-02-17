"""Unit tests for the check_failures handler (doubleday.pipeline.check_failures.handler).

The check_failures Lambda runs after gold load to check whether any silver load
partitions failed during the current pipeline execution. It reads failure records
from S3 (written by the silver_load handler on error) and returns a summary with
the count and list of failed game_dates.

Environment variables are set before import because the handler reads them at
module level.
"""

import io
import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before importing handler (module-level os.environ reads)
os.environ.setdefault("LAKEHOUSE_BUCKET", "test-lakehouse")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.pipeline.check_failures.handler import handler  # noqa: E402


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context for Powertools inject_lambda_context."""
    ctx = MagicMock()
    ctx.function_name = "test-check-failures"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _make_s3_body(record: dict) -> dict:
    """Build a mock S3 GetObject response with a readable Body."""
    return {"Body": io.BytesIO(json.dumps(record).encode())}


class TestCheckFailuresHandler:
    """Tests for the check_failures handler."""

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_no_failures_returns_zero(self, mock_s3, mock_metrics, lambda_context):
        """When no failure objects exist, returns failure_count 0."""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [],
            "IsTruncated": False,
        }

        result = handler({"batch_id": "batch-123"}, lambda_context)

        assert result["failure_count"] == 0
        assert result["failed_game_dates"] == []
        assert result["failure_summary"] == ""

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_no_contents_key_returns_zero(self, mock_s3, mock_metrics, lambda_context):
        """When list_objects_v2 returns no Contents key, returns failure_count 0."""
        mock_s3.list_objects_v2.return_value = {"IsTruncated": False}

        result = handler({"batch_id": "batch-empty"}, lambda_context)

        assert result["failure_count"] == 0
        assert result["failed_game_dates"] == []

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_with_failures(self, mock_s3, mock_metrics, lambda_context):
        """When failure objects exist, returns correct count and dates."""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "failures/silver_load/batch-456/2024-03-02.json"},
                {"Key": "failures/silver_load/batch-456/2024-03-01.json"},
            ],
            "IsTruncated": False,
        }
        mock_s3.get_object.side_effect = [
            _make_s3_body({"game_date": "2024-03-02", "error_message": "bad"}),
            _make_s3_body({"game_date": "2024-03-01", "error_message": "worse"}),
        ]

        result = handler({"batch_id": "batch-456"}, lambda_context)

        assert result["failure_count"] == 2
        assert result["failed_game_dates"] == ["2024-03-01", "2024-03-02"]
        assert "2 game_date(s)" in result["failure_summary"]
        assert "2024-03-01" in result["failure_summary"]
        assert "2024-03-02" in result["failure_summary"]

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_pagination(self, mock_s3, mock_metrics, lambda_context):
        """When S3 response is truncated, handler paginates through all pages."""
        mock_s3.list_objects_v2.side_effect = [
            {
                "Contents": [
                    {"Key": "failures/silver_load/batch-789/2024-04-01.json"},
                ],
                "IsTruncated": True,
                "NextContinuationToken": "token-abc",
            },
            {
                "Contents": [
                    {"Key": "failures/silver_load/batch-789/2024-04-02.json"},
                ],
                "IsTruncated": False,
            },
        ]
        mock_s3.get_object.side_effect = [
            _make_s3_body({"game_date": "2024-04-01", "error_message": "err1"}),
            _make_s3_body({"game_date": "2024-04-02", "error_message": "err2"}),
        ]

        result = handler({"batch_id": "batch-789"}, lambda_context)

        assert result["failure_count"] == 2
        assert result["failed_game_dates"] == ["2024-04-01", "2024-04-02"]
        assert mock_s3.list_objects_v2.call_count == 2
        # Second call should include ContinuationToken
        second_call = mock_s3.list_objects_v2.call_args_list[1]
        assert second_call.kwargs["ContinuationToken"] == "token-abc"

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_uses_correct_prefix(self, mock_s3, mock_metrics, lambda_context):
        """Handler lists S3 objects with the correct prefix for the batch."""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [],
            "IsTruncated": False,
        }

        handler({"batch_id": "my-batch-id"}, lambda_context)

        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket="test-lakehouse",
            Prefix="failures/silver_load/my-batch-id/",
        )

    @patch("doubleday.pipeline.check_failures.handler.metrics")
    @patch("doubleday.pipeline.check_failures.handler.s3")
    @patch("doubleday.pipeline.check_failures.handler.LAKEHOUSE_BUCKET", "test-lakehouse")
    def test_emits_failure_count_metric(self, mock_s3, mock_metrics, lambda_context):
        """Handler emits SilverLoadFailureCount metric."""
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "failures/silver_load/batch-m/2024-05-01.json"},
            ],
            "IsTruncated": False,
        }
        mock_s3.get_object.return_value = _make_s3_body({"game_date": "2024-05-01", "error_message": "err"})

        handler({"batch_id": "batch-m"}, lambda_context)

        calls = mock_metrics.add_metric.call_args_list
        metric_names = [c.kwargs["name"] for c in calls]
        assert "SilverLoadFailureCount" in metric_names
