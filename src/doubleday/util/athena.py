"""Athena query execution and result-reading utilities."""

import time


def run_query(client, sql: str, database: str, output_bucket: str) -> str:
    """Submit a query to Athena and wait for completion.

    Returns the query execution ID.
    """
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": f"s3://{output_bucket}/"},
    )
    execution_id: str = response["QueryExecutionId"]

    while True:
        result = client.get_query_execution(QueryExecutionId=execution_id)
        state = result["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            return execution_id

        if state in ("FAILED", "CANCELLED"):
            reason = result["QueryExecution"]["Status"].get(
                "StateChangeReason", "Unknown"
            )
            raise RuntimeError(f"Query {state}: {reason}")

        # Athena has no push notification — poll get_query_execution until done.
        # 2s is responsive enough for typical 3-10s queries
        # and well under API throttle limits.
        time.sleep(2)


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
