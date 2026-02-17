"""Unit tests for the validate_input handler.

Covers doubleday.pipeline.validate_input.handler.

The validate_input Lambda is the first step in the pipeline Step Function. It
validates that all game_date years match the season, defaults force_download to
False if omitted, and generates a batch_id UUID that tags all staging rows for
the execution (used by clear_staging for bulk cleanup).

No mocking is needed — this handler has no AWS dependencies. It is pure input
validation and normalization.
"""

from unittest.mock import MagicMock

import pytest

from doubleday.pipeline.validate_input.handler import handler


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context for Powertools inject_lambda_context."""
    ctx = MagicMock()
    ctx.function_name = "test-validate-input"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


class TestValidateInputHandler:
    """Tests for the validate_input handler's validation and normalization logic."""

    def test_valid_dates_pass_through(self, lambda_context):
        """Valid dates matching the season are returned unchanged."""
        event = {"season": 2024, "game_dates": ["2024-03-01", "2024-03-02"]}
        result = handler(event, lambda_context)

        assert result["season"] == 2024
        assert result["game_dates"] == ["2024-03-01", "2024-03-02"]

    def test_batch_id_is_generated(self, lambda_context):
        """Output includes a batch_id string."""
        event = {"season": 2024, "game_dates": ["2024-03-01"]}
        result = handler(event, lambda_context)

        assert "batch_id" in result
        assert isinstance(result["batch_id"], str)
        assert len(result["batch_id"]) > 0

    def test_missing_force_download_defaults_to_false(self, lambda_context):
        """Missing force_download defaults to False."""
        event = {"season": 2024, "game_dates": ["2024-03-01"]}
        result = handler(event, lambda_context)

        assert result["force_download"] is False

    def test_force_download_true_preserved(self, lambda_context):
        """Explicit force_download=True is preserved."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01"],
            "force_download": True,
        }
        result = handler(event, lambda_context)

        assert result["force_download"] is True

    def test_force_download_false_preserved(self, lambda_context):
        """Explicit force_download=False is preserved."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01"],
            "force_download": False,
        }
        result = handler(event, lambda_context)

        assert result["force_download"] is False

    def test_invalid_date_year_raises(self, lambda_context):
        """Date with wrong year raises ValueError."""
        event = {"season": 2024, "game_dates": ["2025-03-01"]}

        with pytest.raises(ValueError, match="does not match season"):
            handler(event, lambda_context)

    def test_multiple_dates_one_invalid_raises(self, lambda_context):
        """One bad date among valid ones still raises ValueError."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01", "2025-03-02"],
        }

        with pytest.raises(ValueError, match="2025-03-02"):
            handler(event, lambda_context)

    def test_empty_game_dates(self, lambda_context):
        """Empty game_dates list passes validation."""
        event = {"season": 2024, "game_dates": []}
        result = handler(event, lambda_context)

        assert result["game_dates"] == []
        assert result["force_download"] is False
