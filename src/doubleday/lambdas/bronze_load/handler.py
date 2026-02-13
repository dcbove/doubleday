"""Lambda handler for bronze load — event parsing, metrics, and response building."""

import json
import os
from typing import Any

import boto3
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

from doubleday.lambdas.bronze_load.pipeline import download_partition

s3 = boto3.client("s3")
metrics = Metrics()

BUCKET = os.environ["LAKEHOUSE_BUCKET"]


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Download a single game date from Baseball Savant to S3.

    Args:
        event: Dict with season, game_date, and force_download.
        context: Lambda context (unused).

    Returns:
        Standard Lambda response with download results.
    """
    season = int(event["season"])
    game_date = event["game_date"]
    force_download = event.get("force_download", False)

    metrics.add_dimension(name="season", value=str(season))

    result = download_partition(s3, BUCKET, season, game_date, force_download)

    metrics.add_metric(
        name="RecordsDownloaded",
        unit=MetricUnit.Count,
        value=result.records_downloaded,
    )
    metrics.add_metric(
        name="PartitionSkipped",
        unit=MetricUnit.Count,
        value=int(result.skipped),
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "season": season,
                "game_date": game_date,
                "records_downloaded": result.records_downloaded,
                "skipped": result.skipped,
            }
        ),
    }
