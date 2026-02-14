"""Unit tests for doubleday.lambdas.validate_input.handler."""

import pytest

from doubleday.lambdas.validate_input.handler import handler


class TestValidateInputHandler:
    """Tests for the validate_input handler."""

    def test_valid_dates_pass_through(self):
        """Valid dates matching the season are returned unchanged."""
        event = {"season": 2024, "game_dates": ["2024-03-01", "2024-03-02"]}
        result = handler(event, None)

        assert result["season"] == 2024
        assert result["game_dates"] == ["2024-03-01", "2024-03-02"]

    def test_batch_id_is_generated(self):
        """Output includes a batch_id string."""
        event = {"season": 2024, "game_dates": ["2024-03-01"]}
        result = handler(event, None)

        assert "batch_id" in result
        assert isinstance(result["batch_id"], str)
        assert len(result["batch_id"]) > 0

    def test_missing_force_download_defaults_to_false(self):
        """Missing force_download defaults to False."""
        event = {"season": 2024, "game_dates": ["2024-03-01"]}
        result = handler(event, None)

        assert result["force_download"] is False

    def test_force_download_true_preserved(self):
        """Explicit force_download=True is preserved."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01"],
            "force_download": True,
        }
        result = handler(event, None)

        assert result["force_download"] is True

    def test_force_download_false_preserved(self):
        """Explicit force_download=False is preserved."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01"],
            "force_download": False,
        }
        result = handler(event, None)

        assert result["force_download"] is False

    def test_invalid_date_year_raises(self):
        """Date with wrong year raises ValueError."""
        event = {"season": 2024, "game_dates": ["2025-03-01"]}

        with pytest.raises(ValueError, match="does not match season"):
            handler(event, None)

    def test_multiple_dates_one_invalid_raises(self):
        """One bad date among valid ones still raises ValueError."""
        event = {
            "season": 2024,
            "game_dates": ["2024-03-01", "2025-03-02"],
        }

        with pytest.raises(ValueError, match="2025-03-02"):
            handler(event, None)

    def test_empty_game_dates(self):
        """Empty game_dates list passes validation."""
        event = {"season": 2024, "game_dates": []}
        result = handler(event, None)

        assert result["game_dates"] == []
        assert result["force_download"] is False
