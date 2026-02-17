"""Integration tests for pipeline Lambda functions.

Invokes each deployed Lambda in the dev environment against real AWS resources
(S3, Athena, Iceberg tables). Unlike unit tests which mock AWS clients, these
tests execute actual queries and verify real data flows through the system.

Test partition: season=2024, game_date=2024-03-01 (a known date with Statcast
data). Silver tests clear this partition before each run to ensure a clean state.

Requires:
- Valid AWS credentials with permission to invoke Lambdas and query Athena
- Bronze data already loaded for the test partition (run the pipeline first)
- Deployed dev Lambdas (via terraform apply in the dev environment)

Run with: make test-integration
"""

import json
import uuid
from typing import Any

import boto3
import pytest

from doubleday.util.athena import run_query

lambda_client = boto3.client("lambda")
athena_client = boto3.client("athena")

DATABASE = "doubleday_dev"
OUTPUT_BUCKET = "appleforge-athena-query-results"

SEASON = 2024
GAME_DATE = "2024-03-01"


def _athena_query(sql: str) -> str:
    """Submit a query to Athena and wait for completion."""
    return run_query(athena_client, sql, DATABASE, OUTPUT_BUCKET)


def _count_rows(table: str, where: str) -> int:
    """Count rows in a table matching the given WHERE clause."""
    execution_id = _athena_query(f"SELECT COUNT(*) FROM {table} WHERE {where}")
    result = athena_client.get_query_results(QueryExecutionId=execution_id)
    return int(result["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"])


def _invoke(function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke a Lambda function and return the parsed body."""
    response = lambda_client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload),
    )
    raw = json.loads(response["Payload"].read())

    if "FunctionError" in response:
        pytest.fail(f"{function_name} raised an error: {raw}")

    body: dict[str, Any] = json.loads(raw["body"])
    return body


def _clear_test_partition() -> None:
    """Delete the test partition from silver staging and canonical."""
    _athena_query(f"DELETE FROM silver_pitches_staging " f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'")
    _athena_query(f"DELETE FROM silver_pitches " f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'")


@pytest.mark.integration
class TestBronzeLoad:
    """Test the bronze load Lambda.

    Downloads Statcast CSV from Baseball Savant to S3.
    """

    def test_downloads_partition(self):
        """Invoke bronze load and verify it reports records downloaded."""
        result = _invoke(
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


@pytest.mark.integration
class TestSilverLoad:
    """Test the silver load Lambda — stages, validates, and replaces a silver partition.

    Each test clears the test partition from both staging and canonical before
    running, so the Lambda loads into a known-empty state.
    """

    def setup_method(self):
        """Clear the test partition before each test."""
        _clear_test_partition()

    def test_loads_into_empty_partition(self):
        """Load a partition into an empty canonical table and verify row counts.

        After loading, the number of rows in silver_pitches canonical should
        exactly match the records_loaded count reported by the Lambda (the
        number of rows staged from bronze).
        """
        batch_id = str(uuid.uuid4())
        result = _invoke(
            "doubleday-dev-silver-load",
            {
                "season": SEASON,
                "game_date": GAME_DATE,
                "batch_id": batch_id,
            },
        )

        assert result["records_loaded"] > 0
        assert result["records_inserted"] > 0

        canonical_count = _count_rows(
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

        first = _invoke("doubleday-dev-silver-load", payload)
        second = _invoke("doubleday-dev-silver-load", payload)

        assert second["records_loaded"] == first["records_loaded"]
        assert second["records_inserted"] > 0

        canonical_count = _count_rows(
            "silver_pitches",
            f"season = {SEASON} AND game_date = DATE '{GAME_DATE}'",
        )
        assert canonical_count == first["records_loaded"]


@pytest.mark.integration
class TestGoldLoad:
    """Test the gold load Lambda — rebuilds a gold aggregate table from silver."""

    def test_loads_gold_table(self):
        """Load the gold table and verify rows are inserted."""
        result = _invoke(
            "doubleday-dev-gold-load",
            {
                "table_name": "gold_pitches_shape_season",
                "season": SEASON,
            },
        )

        assert result["records_inserted"] > 0
        assert result["table_name"] == "gold_pitches_shape_season"


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
        _invoke(
            "doubleday-dev-silver-load",
            {
                "season": SEASON,
                "game_date": GAME_DATE,
                "batch_id": batch_id,
            },
        )

        # Clear staging for this batch
        result = _invoke(
            "doubleday-dev-clear-staging",
            {"batch_id": batch_id},
        )

        assert result["batch_id"] == batch_id
        assert "execution_id" in result

        # Verify staging rows are gone for this batch
        staging_count = _count_rows(
            "silver_pitches_staging",
            f"batch_id = '{batch_id}'",
        )
        assert staging_count == 0
