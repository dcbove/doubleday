"""Integration tests for the silver load Lambda.

Invokes the real doubleday-dev-silver-load Lambda against the live Athena/Iceberg
silver tables. Each test starts by deleting the test partition (season=2024,
game_date=2024-03-01) from both the silver pitches staging and silver pitches
canonical tables so that the Lambda runs against a known-empty state.
"""

import json
from typing import Any

import boto3
import pytest

from doubleday.util.athena import run_query

lambda_client = boto3.client("lambda")
athena_client = boto3.client("athena")

FUNCTION_NAME = "doubleday-dev-silver-load"
DATABASE = "doubleday_dev"
OUTPUT_BUCKET = "appleforge-athena-query-results"

PARTITION_NAME = "season=2024/game_date=2024-03-01"
SEASON = 2024
GAME_DATE = "2024-03-01"


def _run_athena_query(sql: str) -> str:
    """Submit a query to Athena and wait for completion."""
    return run_query(athena_client, sql, DATABASE, OUTPUT_BUCKET)


def _count_silver_pitches_canonical_rows() -> int:
    """Count rows in silver pitches canonical for the test partition."""
    execution_id = _run_athena_query(
        f"SELECT COUNT(*) FROM silver_pitches "
        f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'"
    )
    result = athena_client.get_query_results(QueryExecutionId=execution_id)
    return int(result["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"])


def _delete_partition_from_silver_pitches_canonical() -> None:
    """Delete the test partition from silver pitches canonical."""
    _run_athena_query(
        f"DELETE FROM silver_pitches "
        f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'"
    )


def _delete_partition_from_silver_pitches_staging() -> None:
    """Delete the test partition from silver pitches staging."""
    _run_athena_query(
        f"DELETE FROM silver_pitches_staging "
        f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'"
    )


def _invoke(partition_name: str) -> dict[str, Any]:
    """Invoke the silver load Lambda and return the parsed body."""
    response = lambda_client.invoke(
        FunctionName=FUNCTION_NAME,
        Payload=json.dumps({"partition_name": partition_name}),
    )
    payload = json.loads(response["Payload"].read())
    result: dict[str, Any] = json.loads(payload["body"])
    return result


@pytest.mark.integration
class TestSilverPitchesLoadPartition:
    """Test loading a single partition through the silver load Lambda."""

    def setup_method(self):
        """Clear the test partition from silver pitches staging and canonical."""
        _delete_partition_from_silver_pitches_staging()
        _delete_partition_from_silver_pitches_canonical()
        assert _count_silver_pitches_canonical_rows() == 0

    def test_loads_records_into_empty_partition(self):
        """Load a partition into an empty silver pitches canonical table.

        1. Invoke the Lambda for the test partition.
        2. Assert records_loaded > 0 (rows into staging).
        3. Assert records_merged > 0 (rows into canonical).
        4. Assert canonical row count matches records_loaded.
        """
        result = _invoke(PARTITION_NAME)

        assert (
            result["records_loaded"] > 0
        ), f"Expected records loaded into staging, got {result['records_loaded']}"
        assert (
            result["records_merged"] > 0
        ), f"Expected records merged into canonical, got {result['records_merged']}"
        assert _count_silver_pitches_canonical_rows() == result["records_loaded"]

    def test_reload_merges_same_count(self):
        """Reload the same partition and verify idempotency.

        1. Load the test partition (first load into canonical).
        2. Invoke the Lambda again for the same partition.
        3. Assert records_loaded is the same for both.
        4. Assert records_merged > 0 on reload (MERGE updates).
        5. Assert canonical row count unchanged from first load.
        """
        first = _invoke(PARTITION_NAME)
        second = _invoke(PARTITION_NAME)

        assert second["records_loaded"] == first["records_loaded"], (
            f"Expected same records loaded on reload, "
            f"got {second['records_loaded']} vs {first['records_loaded']}"
        )
        assert (
            second["records_merged"] > 0
        ), f"Expected records merged on reload, got {second['records_merged']}"
        assert _count_silver_pitches_canonical_rows() == first["records_loaded"]
