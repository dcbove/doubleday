"""Lambda handler for dimension load — event parsing, metrics, and response building."""

import json
import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from doubleday.pipeline.dimension_load.pipeline import load_dimension

s3 = boto3.client("s3")
athena = boto3.client("athena")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
LAKEHOUSE_BUCKET = os.environ["LAKEHOUSE_BUCKET"]

VALID_DIMENSIONS = {"teams", "venues", "games", "umpires", "players"}


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Load a single dimension table for the given season.

    The Step Function invokes this Lambda once per dimension per pipeline run,
    with all five dimensions running in parallel. Each invocation performs a
    two-phase load:

    1. **Bronze phase**: check S3 for cached JSON; if missing (or
       ``force_download=True``), fetch from the MLB API and write to bronze.
       On subsequent runs the API is not re-called.
    2. **Silver phase**: DELETE the partition → INSERT INTO ... VALUES from
       the bronze data.

    Teams and venues are full-season rebuilds — the entire season partition
    is replaced each run. The bronze cache makes this cheap (no API calls
    after the first run; the Athena cost is a few small queries).

    Games is incremental: only the ``game_dates`` passed in the event are
    deleted and re-inserted, with one bronze file per date.

    Umpires and players use date-scoped discovery when ``game_dates`` is
    provided: only IDs from those dates are queried from silver_games /
    silver_pitches. New IDs are merged into the additive bronze cache,
    and the full cache is loaded into the season partition in silver.

    Args:
        event: Dict with ``dimension`` (str), ``season`` (int), optional
            ``game_dates`` (list[str] — required for games, optional for
            umpires/players to scope incremental queries), and optional
            ``force_download`` (bool, default False).
        context: Lambda context (unused).

    Returns:
        Lambda response with ``records_loaded`` and ``bronze_cached`` status.
    """
    dimension = event["dimension"]
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"Invalid dimension: {dimension}. Must be one of {VALID_DIMENSIONS}")

    season = int(event["season"])
    game_dates = event.get("game_dates", [])
    force_download = event.get("force_download", False)

    metrics.add_dimension(name="dimension", value=dimension)
    metrics.add_dimension(name="season", value=str(season))

    result = load_dimension(
        s3_client=s3,
        athena_client=athena,
        bucket=LAKEHOUSE_BUCKET,
        database=DATABASE,
        output_bucket=OUTPUT_BUCKET,
        dimension=dimension,
        season=season,
        game_dates=game_dates,
        force_download=force_download,
    )

    metrics.add_metric(
        name="RecordsLoaded",
        unit=MetricUnit.Count,
        value=result.records_loaded,
    )
    metrics.add_metric(
        name="BronzeCacheHit",
        unit=MetricUnit.Count,
        value=int(result.bronze_cached),
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "dimension": dimension,
                "season": season,
                "records_loaded": result.records_loaded,
                "bronze_cached": result.bronze_cached,
            }
        ),
    }
