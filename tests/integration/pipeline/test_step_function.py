"""Integration tests for the pipeline Step Function.

The Step Function orchestrates the full ETL pipeline for a single execution:
  1. validate_input — check season/date consistency, generate batch_id
  2. bronze_load — download Statcast CSV for each game_date to S3
  3. silver_load — stage, validate, and replace silver Iceberg partitions
  4. clear_staging — remove staging rows tagged with the execution's batch_id
  5. gold_load — rebuild aggregate gold tables from silver

These tests start real Step Function executions in the dev environment and poll
until completion. Unlike the Lambda-level integration tests (test_lambdas.py)
which invoke individual Lambdas, these verify the full orchestration: that the
Step Function correctly chains Lambdas, passes state between steps, and handles
input validation failures by stopping early.

Test partition: season=2024, game_date=2024-03-01 (a known date with Statcast
data). Silver partition is cleared before each test to ensure a clean state.

Requires:
- Valid AWS credentials with permission to start/describe Step Function executions
  and query Athena
- Bronze data already loaded for the test partition
- Deployed dev infrastructure (Step Function + all Lambdas)

Run with: make test-integration
"""

import json
import time
from typing import Any

import boto3
import pytest

from doubleday.util.athena import run_query

sfn_client = boto3.client("stepfunctions")
athena_client = boto3.client("athena")

DATABASE = "doubleday_dev"
OUTPUT_BUCKET = "appleforge-athena-query-results"

SEASON = 2024
GAME_DATE = "2024-03-01"
STATE_MACHINE_NAME = "doubleday-dev-pipeline"

# Maximum time to wait for a Step Function execution (10 minutes)
EXECUTION_TIMEOUT = 600
POLL_INTERVAL = 10


def _get_state_machine_arn() -> str:
    """Look up the Step Function ARN by name from the account's state machines."""
    paginator = sfn_client.get_paginator("list_state_machines")
    for page in paginator.paginate():
        for sm in page["stateMachines"]:
            if sm["name"] == STATE_MACHINE_NAME:
                return str(sm["stateMachineArn"])
    pytest.fail(f"State machine {STATE_MACHINE_NAME} not found")


def _start_execution(input_payload: dict[str, Any]) -> str:
    """Start a Step Function execution and return the execution ARN."""
    response = sfn_client.start_execution(
        stateMachineArn=_get_state_machine_arn(),
        input=json.dumps(input_payload),
    )
    return str(response["executionArn"])


def _wait_for_execution(execution_arn: str) -> dict[str, Any]:
    """Poll until the execution reaches a terminal state or times out."""
    deadline = time.time() + EXECUTION_TIMEOUT

    while time.time() < deadline:
        response = sfn_client.describe_execution(executionArn=execution_arn)
        status = response["status"]

        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return dict(response)

        time.sleep(POLL_INTERVAL)

    pytest.fail(
        f"Execution {execution_arn} did not complete within {EXECUTION_TIMEOUT}s"
    )


def _athena_query(sql: str) -> str:
    """Submit a query to Athena and wait for completion."""
    return run_query(athena_client, sql, DATABASE, OUTPUT_BUCKET)


def _count_rows(table: str, where: str) -> int:
    """Count rows in a table matching the given WHERE clause."""
    execution_id = _athena_query(f"SELECT COUNT(*) FROM {table} WHERE {where}")
    result = athena_client.get_query_results(QueryExecutionId=execution_id)
    return int(result["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"])


def _clear_test_partition() -> None:
    """Delete the test partition from silver staging and canonical tables.

    Ensures each test starts with a clean silver state so row counts can be
    verified without interference from previous runs.
    """
    _athena_query(
        f"DELETE FROM silver_pitches_staging "
        f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'"
    )
    _athena_query(
        f"DELETE FROM silver_pitches "
        f"WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'"
    )


@pytest.mark.integration
class TestPipelineExecution:
    """Test full pipeline execution via the Step Function.

    Starts real executions and verifies end-to-end data flow: bronze download
    through silver staging/validation through gold aggregation. Also verifies
    that the validate_input step correctly rejects malformed inputs before any
    data processing begins.
    """

    def setup_method(self):
        """Clear the test partition before each test."""
        _clear_test_partition()

    def test_full_pipeline_single_date(self):
        """Run the full pipeline for a single date and verify data flows end-to-end.

        Exercises every step in the Step Function: validate_input → bronze_load →
        silver_load → clear_staging → gold_load. After the execution succeeds,
        verifies that silver canonical and gold aggregate tables contain rows for
        the test partition, confirming data flowed through the entire pipeline.
        """
        execution_arn = _start_execution({"season": SEASON, "game_dates": [GAME_DATE]})

        response = _wait_for_execution(execution_arn)
        assert response["status"] == "SUCCEEDED", (
            f"Pipeline failed: {response.get('error', '')} "
            f"{response.get('cause', '')}"
        )

        # Silver canonical should have rows
        silver_count = _count_rows(
            "silver_pitches",
            f"season = {SEASON} AND game_date = DATE '{GAME_DATE}'",
        )
        assert silver_count > 0, "Expected rows in silver_pitches after pipeline"

        # Gold table should have rows for the season
        gold_count = _count_rows(
            "gold_pitches_shape_season",
            f"season = {SEASON}",
        )
        assert gold_count > 0, "Expected rows in gold_pitches_shape_season"

    def test_mismatched_season_date_fails(self):
        """Verify the pipeline fails fast when game_date year doesn't match season.

        The validate_input Lambda (step 1) rejects inputs where the game_date year
        (2025) doesn't match the season (2024), raising a ValueError that causes
        the Step Function to enter the FAILED state. No data loading occurs.
        """
        execution_arn = _start_execution(
            {"season": SEASON, "game_dates": ["2025-03-01"]}
        )

        response = _wait_for_execution(execution_arn)
        assert response["status"] == "FAILED"
