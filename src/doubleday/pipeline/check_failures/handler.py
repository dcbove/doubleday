"""Lambda handler for check_failures — read silver load failure records from S3."""

import json
import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

s3 = boto3.client("s3")
logger = Logger()
metrics = Metrics()

LAKEHOUSE_BUCKET = os.environ["LAKEHOUSE_BUCKET"]


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Read failure records for a batch and return a summary.

    Args:
        event: Must contain ``batch_id``.
        context: Lambda context (unused).

    Returns:
        Dict with ``failure_count``, ``failed_game_dates``, and
        ``failure_summary``.
    """
    batch_id = event["batch_id"]
    prefix = f"failures/silver_load/{batch_id}/"

    failed_game_dates: list[str] = []
    continuation_token = None

    while True:
        kwargs: dict[str, Any] = {
            "Bucket": LAKEHOUSE_BUCKET,
            "Prefix": prefix,
        }
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**kwargs)

        for obj in response.get("Contents", []):
            body = s3.get_object(Bucket=LAKEHOUSE_BUCKET, Key=obj["Key"])
            record = json.loads(body["Body"].read())
            failed_game_dates.append(record["game_date"])

        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    failed_game_dates.sort()
    failure_count = len(failed_game_dates)

    if failure_count > 0:
        dates_str = ", ".join(failed_game_dates)
        failure_summary = f"Silver load failed for {failure_count} game_date(s): {dates_str}"
    else:
        failure_summary = ""

    logger.info(
        "Failure check complete",
        extra={
            "batch_id": batch_id,
            "failure_count": failure_count,
            "failed_game_dates": failed_game_dates,
        },
    )

    metrics.add_metric(name="SilverLoadFailureCount", unit=MetricUnit.Count, value=failure_count)

    return {
        "failure_count": failure_count,
        "failed_game_dates": failed_game_dates,
        "failure_summary": failure_summary,
    }
