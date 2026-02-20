"""Query neighbors — Athena query and result formatting."""

from dataclasses import dataclass, field
from pathlib import Path

from doubleday.util.athena import get_query_results, run_query

INT_COLUMNS = {"neighbor_pitcher", "neighbor_season", "rank"}
FLOAT_COLUMNS = {"similarity_score"}


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class QueryResult:
    """Result of a shape-neighbors query."""

    pitcher: int
    season: int
    neighbors: list[dict] = field(default_factory=list)


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


def query_neighbors(
    client,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    pitcher: int,
    season: int,
) -> QueryResult:
    """Query pitcher shape-similarity neighbors from the gold table.

    Args:
        client: Boto3 Athena client.
        database: Glue catalog database name.
        output_bucket: S3 bucket for Athena query results.
        sql_dir: Path to the SQL template directory.
        pitcher: The pitcher's MLB ID.
        season: The season year.

    Returns:
        QueryResult with pitcher, season, and list of neighbor dicts.
    """
    sql = load_sql(sql_dir, "api/query_neighbors.sql").format(pitcher=pitcher, season=season)

    execution_id = run_query(client, sql, database, output_bucket)
    rows = get_query_results(client, execution_id)
    neighbors = [_coerce_row(row) for row in rows]

    return QueryResult(pitcher=pitcher, season=season, neighbors=neighbors)
