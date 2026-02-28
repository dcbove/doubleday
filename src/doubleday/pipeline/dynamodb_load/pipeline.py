"""DynamoDB load pipeline — read gold tables via Athena and batch-write to DynamoDB."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

from aws_lambda_powertools import Logger

from doubleday.util.athena import get_query_results, run_query

logger = Logger(child=True)


class _EntityConfig(TypedDict):
    sql_file: str
    pk_builder: Callable[[dict[str, str]], str]
    sk_builder: Callable[[dict[str, str]], str]
    entity_type_value: str


ENTITY_CONFIG: dict[str, _EntityConfig] = {
    "pitches": {
        "sql_file": "pipeline/dynamodb_load_pitches.sql",
        "pk_builder": lambda row: f"PITCHER#{row['pitcher']}#SEASON#{row['season']}",
        "sk_builder": lambda row: f"PITCH#{row['pitch_type']}",
        "entity_type_value": "pitch",
    },
    "neighbors": {
        "sql_file": "pipeline/dynamodb_load_neighbors.sql",
        "pk_builder": lambda row: (f"PITCHER#{row['source_pitcher']}#SEASON#{row['source_season']}"),
        "sk_builder": lambda row: f"NEIGHBOR#{int(row['rank']):03d}",
        "entity_type_value": "neighbor",
    },
}

PITCHES_NUMBER_COLUMNS = {
    "pitcher",
    "season",
    "pitch_count",
    "avg_horz_break_in",
    "avg_vert_break_in",
    "stddev_horz_break_in",
    "stddev_vert_break_in",
    "p10_horz_break_in",
    "p90_horz_break_in",
    "p10_vert_break_in",
    "p90_vert_break_in",
    "avg_velocity",
    "p10_velocity",
    "p90_velocity",
    "avg_adj_velocity",
    "avg_spin_rate",
    "usage_rate",
}

NEIGHBORS_NUMBER_COLUMNS = {
    "neighbor_pitcher",
    "neighbor_season",
    "rank",
    "similarity_score",
}


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class DynamoDBLoadResult:
    """Result of a DynamoDB load operation."""

    records_loaded: int
    records_deleted: int


def _coerce_to_dynamodb(value: str, column: str, number_columns: set[str]) -> str | Decimal | None:
    """Coerce an Athena string value to a DynamoDB-compatible type."""
    if not value or value == "":
        return None
    if column in number_columns:
        return Decimal(value)
    return value


def _delete_existing_items(table, sk_prefix: str, season: int) -> int:
    """Delete all existing items for an entity type and season.

    Scans the table for items matching the SK prefix and season, then
    batch-deletes them. Data volumes are small (~3K-14K items per season),
    making scan practical during pipeline runs.

    Args:
        table: Boto3 DynamoDB Table resource.
        sk_prefix: Sort key prefix to match (e.g. ``"PITCH#"``).
        season: Season year to filter on.

    Returns:
        Number of items deleted.
    """
    deleted = 0
    scan_kwargs: dict = {
        "FilterExpression": "begins_with(SK, :sk_prefix) AND season = :season",
        "ExpressionAttributeValues": {
            ":sk_prefix": sk_prefix,
            ":season": season,
        },
        "ProjectionExpression": "PK, SK",
    }

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                deleted += 1

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    logger.info("Deleted existing items", extra={"deleted": deleted, "sk_prefix": sk_prefix})
    return deleted


def load_to_dynamodb(
    athena_client,
    table,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    entity_type: str,
    season: int,
) -> DynamoDBLoadResult:
    """Load gold data for an entity type and season into DynamoDB.

    Reads the gold Iceberg table via Athena, deletes any existing items for
    that entity/season, then batch-writes fresh items to DynamoDB.

    Args:
        athena_client: Boto3 Athena client.
        table: Boto3 DynamoDB Table resource.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        sql_dir: Path to SQL template directory.
        entity_type: ``"pitches"`` or ``"neighbors"``.
        season: Season year to load.

    Returns:
        DynamoDBLoadResult with counts of records loaded and deleted.
    """
    config = ENTITY_CONFIG[entity_type]
    number_columns = PITCHES_NUMBER_COLUMNS if entity_type == "pitches" else NEIGHBORS_NUMBER_COLUMNS

    sql = load_sql(sql_dir, config["sql_file"]).format(season=season)
    logger.info("Querying gold data", extra={"entity_type": entity_type, "season": season})
    execution_id = run_query(athena_client, sql, database, output_bucket)
    rows = get_query_results(athena_client, execution_id)
    logger.info("Query returned rows", extra={"count": len(rows)})

    sk_prefix = "PITCH#" if entity_type == "pitches" else "NEIGHBOR#"
    records_deleted = _delete_existing_items(table, sk_prefix, season)

    items = []
    for row in rows:
        item: dict = {
            "PK": config["pk_builder"](row),
            "SK": config["sk_builder"](row),
            "entity_type": config["entity_type_value"],
        }
        for col, val in row.items():
            coerced = _coerce_to_dynamodb(val, col, number_columns)
            if coerced is not None:
                item[col] = coerced
        items.append(item)

    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    records_loaded = len(items)

    logger.info("Loaded items", extra={"records_loaded": records_loaded})
    return DynamoDBLoadResult(records_loaded=records_loaded, records_deleted=records_deleted)
