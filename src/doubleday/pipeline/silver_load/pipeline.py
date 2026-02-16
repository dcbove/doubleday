"""Silver load pipeline.

Stage, validate, and replace partitions from bronze to silver.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from doubleday.util.athena import get_query_row_count, run_query

STEPS = [
    ("load_partition", "silver_load_partition_into_staging_table.sql"),
    ("validate_staging", "silver_validate_staging_table.sql"),
    ("delete_canonical", "silver_delete_partition_from_canonical_table.sql"),
    ("insert_canonical", "silver_insert_partition_into_canonical_table.sql"),
]


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class LoadResult:
    """Result of a silver load partition run."""

    records_loaded: int
    records_inserted: int
    results: dict[str, str]


def load_partition(
    client,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    season: int,
    game_date: str,
    batch_id: str,
) -> LoadResult:
    """Run the full silver load pipeline for a single partition."""
    run_id = str(uuid.uuid4())
    fmt = {
        "season": season,
        "game_date": game_date,
        "run_id": run_id,
        "batch_id": batch_id,
    }

    records_loaded = 0
    records_inserted = 0
    results = {}
    for step_name, sql_file in STEPS:
        sql = load_sql(sql_dir, sql_file).format(**fmt)
        print(f"Running {step_name}: {sql_file}")
        execution_id = run_query(client, sql, database, output_bucket)
        results[step_name] = execution_id
        print(f"  Completed: {execution_id}")

        if step_name == "load_partition":
            records_loaded = get_query_row_count(client, execution_id)
            print(f"  Records loaded into staging: {records_loaded}")

        if step_name == "validate_staging":
            duplicate_keys = get_query_row_count(client, execution_id)
            if duplicate_keys > 0:
                raise ValueError(
                    f"Staging validation failed: {duplicate_keys} duplicate "
                    f"(game_pk, at_bat_number, pitch_number) keys found "
                    f"for season={season}, game_date={game_date}"
                )
            print("  Validation passed: no duplicate keys")

        if step_name == "insert_canonical":
            records_inserted = get_query_row_count(client, execution_id)
            print(f"  Records inserted into canonical: {records_inserted}")

    return LoadResult(
        records_loaded=records_loaded,
        records_inserted=records_inserted,
        results=results,
    )
