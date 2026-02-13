"""Silver load pipeline.

Stage, validate, and merge partitions from bronze to silver.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from doubleday.util.athena import get_query_row_count, run_query

STEPS = [
    ("clear_staging_pre", "silver_clear_partition_from_staging_table.sql"),
    ("load_partition", "silver_load_partition_into_staging_table.sql"),
    ("validate_staging", "silver_validate_staging_table.sql"),
    ("merge_partition", "silver_merge_partition_into_canonical_table.sql"),
    ("clear_staging_post", "silver_clear_partition_from_staging_table.sql"),
]


def parse_partition_name(partition_name: str) -> tuple[int, str]:
    """Parse 'season=2025/game_date=2025-03-27' into (2025, '2025-03-27')."""
    match = re.match(r"season=(\d+)/game_date=(\d{4}-\d{2}-\d{2})", partition_name)
    if not match:
        raise ValueError(
            f"Invalid partition_name: {partition_name}. "
            "Expected format: season=YYYY/game_date=YYYY-MM-DD"
        )
    return int(match.group(1)), match.group(2)


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class LoadResult:
    """Result of a silver load partition run."""

    records_loaded: int
    records_merged: int
    results: dict[str, str]


def load_partition(
    client,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    season: int,
    game_date: str,
) -> LoadResult:
    """Run the full silver load pipeline for a single partition."""
    fmt = {"season": season, "game_date": game_date}

    records_loaded = 0
    records_merged = 0
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

        if step_name == "merge_partition":
            records_merged = get_query_row_count(client, execution_id)
            print(f"  Records merged into canonical: {records_merged}")

    return LoadResult(
        records_loaded=records_loaded,
        records_merged=records_merged,
        results=results,
    )
