"""Unit tests for the daily_trigger handler (doubleday.pipeline.daily_trigger.handler).

The daily_trigger Lambda is invoked by EventBridge Scheduler every day at 9 AM ET.
It computes yesterday's date in Eastern Time, derives the season year, and starts
the pipeline Step Function with the standard ``{season, game_dates}`` input.

Environment variables are set before import because the handler reads them at
module level.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

# Set env vars before importing handler (module-level os.environ reads)
os.environ.setdefault("STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456:stateMachine:test")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "Test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")

from doubleday.pipeline.daily_trigger.handler import handler  # noqa: E402

ET = ZoneInfo("America/New_York")


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context for Powertools inject_lambda_context."""
    ctx = MagicMock()
    ctx.function_name = "test-daily-trigger"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


class TestDailyTriggerHandler:
    """Tests for the daily_trigger handler."""

    @patch("doubleday.pipeline.daily_trigger.handler.metrics")
    @patch("doubleday.pipeline.daily_trigger.handler.sfn")
    @patch("doubleday.pipeline.daily_trigger.handler.datetime")
    def test_mid_year_yesterday(self, mock_datetime, mock_sfn, mock_metrics, lambda_context):
        """Mid-year date correctly computes yesterday and season."""
        mock_datetime.now.return_value = datetime(2024, 7, 15, 9, 0, tzinfo=ET)
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456:execution:test:abc",
        }

        result = handler({}, lambda_context)

        assert result["game_date"] == "2024-07-14"
        assert result["season"] == 2024
        assert result["execution_arn"] == "arn:aws:states:us-east-1:123456:execution:test:abc"

    @patch("doubleday.pipeline.daily_trigger.handler.metrics")
    @patch("doubleday.pipeline.daily_trigger.handler.sfn")
    @patch("doubleday.pipeline.daily_trigger.handler.datetime")
    def test_jan_1_boundary(self, mock_datetime, mock_sfn, mock_metrics, lambda_context):
        """Jan 1 correctly yields Dec 31 of the previous year."""
        mock_datetime.now.return_value = datetime(2025, 1, 1, 9, 0, tzinfo=ET)
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456:execution:test:xyz",
        }

        result = handler({}, lambda_context)

        assert result["game_date"] == "2024-12-31"
        assert result["season"] == 2024

    @patch("doubleday.pipeline.daily_trigger.handler.metrics")
    @patch("doubleday.pipeline.daily_trigger.handler.sfn")
    @patch("doubleday.pipeline.daily_trigger.handler.datetime")
    def test_correct_state_machine_arn(self, mock_datetime, mock_sfn, mock_metrics, lambda_context):
        """Handler passes the correct state machine ARN to start_execution."""
        mock_datetime.now.return_value = datetime(2024, 6, 10, 9, 0, tzinfo=ET)
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_sfn.start_execution.return_value = {"executionArn": "arn:test"}

        handler({}, lambda_context)

        call_kwargs = mock_sfn.start_execution.call_args.kwargs
        assert call_kwargs["stateMachineArn"] == "arn:aws:states:us-east-1:123456:stateMachine:test"

    @patch("doubleday.pipeline.daily_trigger.handler.metrics")
    @patch("doubleday.pipeline.daily_trigger.handler.sfn")
    @patch("doubleday.pipeline.daily_trigger.handler.datetime")
    def test_sfn_input_format(self, mock_datetime, mock_sfn, mock_metrics, lambda_context):
        """Handler sends correctly formatted JSON input to Step Functions."""
        mock_datetime.now.return_value = datetime(2024, 4, 20, 9, 0, tzinfo=ET)
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_sfn.start_execution.return_value = {"executionArn": "arn:test"}

        handler({}, lambda_context)

        import json

        call_kwargs = mock_sfn.start_execution.call_args.kwargs
        parsed_input = json.loads(call_kwargs["input"])
        assert parsed_input == {"season": 2024, "game_dates": ["2024-04-19"]}

    @patch("doubleday.pipeline.daily_trigger.handler.metrics")
    @patch("doubleday.pipeline.daily_trigger.handler.sfn")
    @patch("doubleday.pipeline.daily_trigger.handler.datetime")
    def test_emits_metric(self, mock_datetime, mock_sfn, mock_metrics, lambda_context):
        """Handler emits DailyTriggerExecutionStarted metric."""
        mock_datetime.now.return_value = datetime(2024, 8, 1, 9, 0, tzinfo=ET)
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_sfn.start_execution.return_value = {"executionArn": "arn:test"}

        handler({}, lambda_context)

        calls = mock_metrics.add_metric.call_args_list
        metric_names = [c.kwargs["name"] for c in calls]
        assert "DailyTriggerExecutionStarted" in metric_names
