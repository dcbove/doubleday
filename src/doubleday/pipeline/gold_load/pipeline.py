"""Gold load pipeline — partition overwrite from silver to gold."""

from dataclasses import dataclass
from pathlib import Path

from aws_lambda_powertools import Logger

from doubleday.util.athena import get_query_row_count, run_query

logger = Logger(child=True)

STEPS = [
    ("delete_partition", "pipeline/{table_name}_delete.sql"),
    ("insert_partition", "pipeline/{table_name}_insert.sql"),
]


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


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

    Executes a DELETE then INSERT, each from its own SQL file.
    """
    records_inserted = 0
    results: dict[str, str] = {}
    for step_name, sql_file_template in STEPS:
        sql_file = sql_file_template.format(table_name=table_name)
        sql = load_sql(sql_dir, sql_file).format(season=season)
        logger.info("Running step", extra={"step": step_name, "sql_file": sql_file})
        execution_id = run_query(client, sql, database, output_bucket)
        results[step_name] = execution_id
        logger.info(
            "Step completed",
            extra={"step": step_name, "execution_id": execution_id},
        )

        if step_name == "insert_partition":
            records_inserted = get_query_row_count(client, execution_id)
            logger.info(
                "Records inserted",
                extra={"records_inserted": records_inserted},
            )

    return LoadResult(records_inserted=records_inserted, results=results)
