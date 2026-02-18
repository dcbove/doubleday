"""Integration tests for silver load and clear staging Lambdas.

Silver load stages, validates, and replaces silver Iceberg partitions.
Clear staging bulk-deletes staging rows by batch_id.

Test partition: season=2024, game_date=2024-03-01 (a known date with Statcast
data). Silver tests clear this partition before each run to ensure a clean state.

Requires:
- Valid AWS credentials with permission to invoke Lambdas and query Athena
- Bronze data already loaded for the test partition (run the pipeline first)
- Deployed dev Lambdas (via terraform apply in the dev environment)

Run with: make test-integration
"""

import uuid

import pytest

from tests.integration.pipeline.conftest import (
    GAME_DATE,
    SEASON,
    clear_test_partition,
    count_rows,
    invoke_lambda,
)


@pytest.mark.integration
class TestSilverLoad:
    """Test the silver load Lambda — stages, validates, and replaces a silver partition.

    Each test clears the test partition from both staging and canonical before
    running, so the Lambda loads into a known-empty state.
    """

    def setup_method(self):
        """Clear the test partition before each test."""
        clear_test_partition()

    def test_loads_into_empty_partition(self):
        """Load a partition into an empty canonical table and verify row counts.

        After loading, the number of rows in silver_pitches canonical should
        exactly match the records_loaded count reported by the Lambda (the
        number of rows staged from bronze).
        """
        batch_id = str(uuid.uuid4())
        result = invoke_lambda(
            "doubleday-dev-silver-load",
            {
                "season": SEASON,
                "game_date": GAME_DATE,
                "batch_id": batch_id,
            },
        )

        assert result["records_loaded"] > 0
        assert result["records_inserted"] > 0

        canonical_count = count_rows(
            "silver_pitches",
            f"season = {SEASON} AND game_date = DATE '{GAME_DATE}'",
        )
        assert canonical_count == result["records_loaded"]

    def test_reload_is_idempotent(self):
        """Reload the same partition twice and verify canonical row count is unchanged.

        The silver load uses DELETE + INSERT (not MERGE), so reloading the same
        partition should produce the exact same row count — no duplicates.
        """
        batch_id = str(uuid.uuid4())
        payload = {
            "season": SEASON,
            "game_date": GAME_DATE,
            "batch_id": batch_id,
        }

        first = invoke_lambda("doubleday-dev-silver-load", payload)
        second = invoke_lambda("doubleday-dev-silver-load", payload)

        assert second["records_loaded"] == first["records_loaded"]
        assert second["records_inserted"] > 0

        canonical_count = count_rows(
            "silver_pitches",
            f"season = {SEASON} AND game_date = DATE '{GAME_DATE}'",
        )
        assert canonical_count == first["records_loaded"]


@pytest.mark.integration
class TestClearStaging:
    """Test the clear staging Lambda — bulk-deletes staging rows by batch_id.

    First loads data via silver_load (which creates staging rows tagged with a
    batch_id), then invokes clear_staging and verifies those rows are gone.
    """

    def test_clears_batch(self):
        """Load a partition into staging, then clear it by batch_id."""
        batch_id = str(uuid.uuid4())

        # Load some data into staging
        invoke_lambda(
            "doubleday-dev-silver-load",
            {
                "season": SEASON,
                "game_date": GAME_DATE,
                "batch_id": batch_id,
            },
        )

        # Clear staging for this batch
        result = invoke_lambda(
            "doubleday-dev-clear-staging",
            {"batch_id": batch_id},
        )

        assert result["batch_id"] == batch_id
        assert "execution_id" in result

        # Verify staging rows are gone for this batch
        staging_count = count_rows(
            "silver_pitches_staging",
            f"batch_id = '{batch_id}'",
        )
        assert staging_count == 0
