"""SQL generation utilities for Athena INSERT INTO ... VALUES statements.

Provides helpers for building batched INSERT statements from in-memory data,
used by the dimension load pipeline to write small dimension tables (teams,
venues, games, umpires, players) directly via Athena rather than going
through a Glue external table.
"""

from aws_lambda_powertools import Logger

logger = Logger(child=True)


def _escape_value(value: object) -> str:
    """Escape a single value for inclusion in a SQL VALUES clause.

    Args:
        value: The Python value to escape. Supported types: str, int, float,
            bool, None.

    Returns:
        SQL literal string: quoted string, numeric literal, boolean literal,
        or NULL.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    # String: double single quotes for SQL escaping
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def build_values_insert(
    table: str,
    columns: list[str],
    rows: list[dict],
    batch_size: int = 100,
) -> list[str]:
    """Generate batched INSERT INTO ... VALUES SQL statements.

    Splits the input rows into batches of ``batch_size`` and generates one
    INSERT statement per batch. Each row is a dict mapping column names to
    values.

    Args:
        table: Target Iceberg table name (e.g. "silver_teams").
        columns: Ordered list of column names for the INSERT.
        rows: List of dicts, each mapping column names to values.
        batch_size: Maximum rows per INSERT statement (default 100).

    Returns:
        List of SQL INSERT strings. Empty list if rows is empty.
    """
    if not rows:
        return []

    statements: list[str] = []
    col_list = ", ".join(columns)

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        value_rows: list[str] = []
        for row in batch:
            values = ", ".join(_escape_value(row.get(col)) for col in columns)
            value_rows.append(f"({values})")
        values_clause = ",\n".join(value_rows)
        sql = f"INSERT INTO {table} ({col_list})\nVALUES\n{values_clause}"
        statements.append(sql)

    logger.info(
        "Generated INSERT statements",
        extra={
            "table": table,
            "total_rows": len(rows),
            "statements": len(statements),
        },
    )
    return statements
