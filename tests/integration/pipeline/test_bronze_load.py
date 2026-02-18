"""Integration tests for the bronze load Lambda.

Downloads Statcast CSV from Baseball Savant to S3.

Requires:
- Valid AWS credentials with permission to invoke Lambdas
- Deployed dev Lambdas (via terraform apply in the dev environment)

Run with: make test-integration
"""

import pytest

from tests.integration.pipeline.conftest import GAME_DATE, SEASON, invoke_lambda


@pytest.mark.integration
class TestBronzeLoad:
    """Test the bronze load Lambda.

    Downloads Statcast CSV from Baseball Savant to S3.
    """

    def test_downloads_partition(self):
        """Invoke bronze load and verify it reports records downloaded."""
        result = invoke_lambda(
            "doubleday-dev-bronze-load",
            {
                "season": SEASON,
                "game_date": GAME_DATE,
                "force_download": False,
            },
        )

        assert result["season"] == SEASON
        assert result["game_date"] == GAME_DATE
        # Either downloaded new data or skipped (already in S3)
        assert result["records_downloaded"] > 0 or result["skipped"] is True
