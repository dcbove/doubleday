"""Query pitches — Athena query and result formatting."""

from dataclasses import dataclass, field
from pathlib import Path

from doubleday.util.athena import get_query_results, run_query

INT_COLUMNS = {"pitcher", "pitch_count", "season"}
FLOAT_COLUMNS = {
    "avg_horz_break",
    "avg_ivb",
    "stddev_horz_break",
    "stddev_ivb",
    "p10_horz_break",
    "p90_horz_break",
    "p10_ivb",
    "p90_ivb",
    "avg_velocity",
    "p10_velocity",
    "p90_velocity",
    "avg_adj_velocity",
    "avg_spin_rate",
    "usage_rate",
}


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class QueryResult:
    """Result of a pitch-shape query."""

    pitcher: int
    season: int
    pitches: list[dict] = field(default_factory=list)


def _coerce_row(row: dict[str, str]) -> dict:
    """Coerce Athena string values to typed Python values."""
    typed: dict = {}
    for key, value in row.items():
        if key in INT_COLUMNS:
            typed[key] = int(value)
        elif key in FLOAT_COLUMNS:
            typed[key] = float(value)
        else:
            typed[key] = value
    return typed


def query_pitches(
    client,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    pitcher: int,
    season: int,
    pitch_type: str | None = None,
) -> QueryResult:
    """Query pitcher pitch-shape stats from the gold table.

    Args:
        client: Boto3 Athena client.
        database: Glue catalog database name.
        output_bucket: S3 bucket for Athena query results.
        sql_dir: Path to the SQL template directory.
        pitcher: The pitcher's MLB ID.
        season: The season year.
        pitch_type: Optional pitch type filter (e.g. 'FF', 'SL').

    Returns:
        QueryResult with pitcher, season, and list of pitch-shape dicts.
    """
    sql = load_sql(sql_dir, "api/query_pitches.sql").format(pitcher=pitcher, season=season)

    if pitch_type is not None:
        sql += f"\n  AND pitch_type = '{pitch_type}'"

    execution_id = run_query(client, sql, database, output_bucket)
    rows = get_query_results(client, execution_id)
    pitches = [_coerce_row(row) for row in rows]

    return QueryResult(pitcher=pitcher, season=season, pitches=pitches)
