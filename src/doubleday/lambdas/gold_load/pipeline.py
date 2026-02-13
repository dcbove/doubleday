"""Gold load pipeline — partition overwrite from silver to gold."""

from dataclasses import dataclass
from pathlib import Path

from doubleday.util.athena import get_query_row_count, run_query


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


def split_statements(sql: str) -> list[str]:
    """Split a SQL file into individual statements on semicolons.

    Strips comments-only fragments and whitespace-only fragments.
    """
    return [s.strip() for s in sql.split(";") if s.strip() and not _is_comment_only(s)]


def _is_comment_only(sql: str) -> bool:
    """Return True if the SQL fragment contains only comments and whitespace."""
    lines = sql.strip().splitlines()
    return all(line.strip() == "" or line.strip().startswith("--") for line in lines)


@dataclass
class LoadResult:
    """Result of a gold load partition run."""

    records_inserted: int
    results: dict[str, str]


def load_table(
    client,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    table_name: str,
    season: int,
) -> LoadResult:
    """Run the gold load pipeline for a single table and season.

    Reads the SQL file for the given table, splits into statements (DELETE + INSERT),
    and executes each in order.
    """
    sql_file = f"{table_name}.sql"
    raw_sql = load_sql(sql_dir, sql_file).format(season=season)
    statements = split_statements(raw_sql)

    records_inserted = 0
    results: dict[str, str] = {}
    for i, stmt in enumerate(statements):
        step_name = "delete_partition" if i == 0 else "insert_partition"
        print(f"Running {step_name}: {sql_file} (statement {i + 1}/{len(statements)})")
        execution_id = run_query(client, stmt, database, output_bucket)
        results[step_name] = execution_id
        print(f"  Completed: {execution_id}")

        if step_name == "insert_partition":
            records_inserted = get_query_row_count(client, execution_id)
            print(f"  Records inserted: {records_inserted}")

    return LoadResult(records_inserted=records_inserted, results=results)
