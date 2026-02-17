"""Athena query execution and result-reading utilities."""

import random
import time

from aws_lambda_powertools import Logger

logger = Logger(child=True)


def run_query(client, sql: str, database: str, output_bucket: str) -> str:
    """Submit a query to Athena and wait for completion. Returns QueryExecutionId."""
    max_attempts = 8

    for attempt in range(1, max_attempts + 1):
        response = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": f"s3://{output_bucket}/"},
        )
        execution_id: str = response["QueryExecutionId"]
        logger.info("Query submitted", extra={"execution_id": execution_id})

        while True:
            result = client.get_query_execution(QueryExecutionId=execution_id)
            state = result["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                return execution_id

            if state in ("FAILED", "CANCELLED"):
                reason = result["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown"
                )

                # Retry only Iceberg commit conflicts
                if "ICEBERG_COMMIT_ERROR" in reason and attempt < max_attempts:
                    # exponential backoff + jitter
                    base = min(30.0, 1.0 * (2 ** (attempt - 1)))
                    logger.warning(
                        "Iceberg commit conflict, retrying",
                        extra={
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "execution_id": execution_id,
                        },
                    )
                    time.sleep(random.uniform(0.5 * base, 1.5 * base))
                    break  # retry: start a new query execution

                logger.error(
                    "Query failed",
                    extra={
                        "state": state,
                        "reason": reason,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "execution_id": execution_id,
                    },
                )
                raise RuntimeError(
                    f"Query {state}: {reason} " f"(attempt {attempt}/{max_attempts})"
                )

            time.sleep(2)

    # logically unreachable, but keeps type-checkers happy
    raise RuntimeError("run_query: exhausted retries unexpectedly")


def get_query_results(client, execution_id: str) -> list[dict[str, str]]:
    """Fetch all result rows from a completed SELECT query as a list of dicts.

    Args:
        client: Boto3 Athena client.
        execution_id: The QueryExecutionId of the completed query.

    Returns:
        List of dicts mapping column names to string values.
    """
    rows: list[dict[str, str]] = []
    kwargs: dict = {"QueryExecutionId": execution_id}
    is_first_page = True

    while True:
        result = client.get_query_results(**kwargs)
        columns = [
            col["Name"]
            for col in result["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
        ]
        page_rows = result["ResultSet"]["Rows"]

        # Skip header row (first row of first page)
        start = 1 if is_first_page else 0
        is_first_page = False

        for row in page_rows[start:]:
            values = [field.get("VarCharValue", "") for field in row["Data"]]
            rows.append(dict(zip(columns, values, strict=True)))

        next_token = result.get("NextToken")
        if not next_token:
            break
        kwargs["NextToken"] = next_token

    return rows


def get_query_row_count(client, execution_id: str) -> int:
    """Get the row count from a completed INSERT/MERGE query result.

    Athena returns counts in different places depending on the operation:
    - INSERT INTO Iceberg: count in ResultSet.Rows[1]
    - MERGE INTO Iceberg: count in UpdateCount (Rows is empty)
    """
    result = client.get_query_results(QueryExecutionId=execution_id)
    update_count = int(result.get("UpdateCount", 0))
    if update_count:
        return update_count
    rows = result["ResultSet"]["Rows"]
    if len(rows) >= 2:
        return int(rows[1]["Data"][0]["VarCharValue"])
    return 0
