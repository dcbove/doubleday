"""Lambda handler for catalog build — event parsing, metrics, and response building.

Expects an event with ``season`` (int) and ``role`` ("pitchers" or "batters").
Delegates to ``build_catalog_for_role`` in the pipeline module, then emits
CloudWatch metrics for player count, team count, catalog size, and enrichment
cache hit/miss rates.
"""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

import doubleday
from doubleday.pipeline.catalog_build.pipeline import build_catalog_for_role

athena = boto3.client("athena")
s3 = boto3.client("s3")
logger = Logger()
metrics = Metrics()

DATABASE = os.environ["GLUE_DATABASE"]
OUTPUT_BUCKET = os.environ["ATHENA_OUTPUT_BUCKET"]
LAKEHOUSE_BUCKET = os.environ["LAKEHOUSE_BUCKET"]
FRONTEND_BUCKET = os.environ["FRONTEND_BUCKET"]
SQL_DIR = Path(doubleday.__file__).parent / "sql"


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Build and publish a player catalog for a single season and role.

    Args:
        event: Dict with ``season`` (int) and ``role`` (str) keys.
        context: Lambda context (unused, required by the runtime contract).

    Returns:
        API-style response with statusCode 200 and a JSON body containing
        season, role, player_count, team_count, catalog_bytes, and
        last_known_good.
    """
    season = int(event["season"])
    role = event["role"]
    force_rebuild = event.get("force_rebuild", False)

    metrics.add_dimension(name="role", value=role)
    metrics.add_dimension(name="season", value=str(season))

    result = build_catalog_for_role(
        athena,
        s3,
        DATABASE,
        OUTPUT_BUCKET,
        LAKEHOUSE_BUCKET,
        FRONTEND_BUCKET,
        SQL_DIR,
        season,
        role,
        force_rebuild=force_rebuild,
    )

    metrics.add_metric(name="PlayerCount", unit=MetricUnit.Count, value=result.player_count)
    metrics.add_metric(name="TeamCount", unit=MetricUnit.Count, value=result.team_count)
    metrics.add_metric(name="CatalogBytes", unit=MetricUnit.Count, value=result.catalog_bytes)
    metrics.add_metric(name="EnrichmentCacheHit", unit=MetricUnit.Count, value=result.enrichment_cache_hit)
    metrics.add_metric(name="EnrichmentApiHit", unit=MetricUnit.Count, value=result.enrichment_api_hit)
    metrics.add_metric(name="EnrichmentMissing", unit=MetricUnit.Count, value=result.enrichment_missing)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "season": season,
                "role": role,
                "player_count": result.player_count,
                "team_count": result.team_count,
                "catalog_bytes": result.catalog_bytes,
                "last_known_good": result.last_known_good,
            }
        ),
    }
