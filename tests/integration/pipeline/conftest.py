"""Shared helpers and constants for pipeline integration tests.

Provides Athena query helpers, Lambda invocation, and partition cleanup
used by both Lambda-level and Step Function-level integration tests.

Test partition: season=2024, game_date=2024-03-01 (a known date with Statcast
data).
"""

import json
from typing import Any

import boto3
import pytest

from doubleday.util.athena import run_query

lambda_client = boto3.client("lambda")
athena_client = boto3.client("athena")

DATABASE = "doubleday_dev"
OUTPUT_BUCKET = "appleforge-athena-query-results"

SEASON = 2024
GAME_DATE = "2024-04-15"


def athena_query(sql: str) -> str:
    """Submit a query to Athena and wait for completion."""
    return run_query(athena_client, sql, DATABASE, OUTPUT_BUCKET)


def count_rows(table: str, where: str) -> int:
    """Count rows in a table matching the given WHERE clause."""
    execution_id = athena_query(f"SELECT COUNT(*) FROM {table} WHERE {where}")
    result = athena_client.get_query_results(QueryExecutionId=execution_id)
    return int(result["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"])


def invoke_lambda(function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
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


def clear_test_partition() -> None:
    """Delete the test partition from silver staging and canonical."""
    athena_query(f"DELETE FROM silver_pitches_staging WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'")
    athena_query(f"DELETE FROM silver_pitches WHERE season = {SEASON} AND game_date = DATE '{GAME_DATE}'")
