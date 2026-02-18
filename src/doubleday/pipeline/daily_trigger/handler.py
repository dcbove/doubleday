"""Lambda handler for daily_trigger — start the pipeline for yesterday's games."""

import json
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

sfn = boto3.client("stepfunctions")
logger = Logger()
metrics = Metrics()

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
ET = ZoneInfo("America/New_York")


@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Compute yesterday's date in ET and start a pipeline execution.

    Args:
        event: EventBridge Scheduler payload (ignored).
        context: Lambda context (unused).

    Returns:
        Dict with ``execution_arn``, ``game_date``, and ``season``.
    """
    now = datetime.now(tz=ET)
    yesterday = now - timedelta(days=1)
    game_date = yesterday.strftime("%Y-%m-%d")
    season = yesterday.year

    sfn_input = json.dumps({"season": season, "game_dates": [game_date]})

    logger.info(
        "Starting pipeline execution",
        extra={"game_date": game_date, "season": season},
    )

    response = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=sfn_input,
    )

    execution_arn = response["executionArn"]

    metrics.add_metric(
        name="DailyTriggerExecutionStarted",
        unit=MetricUnit.Count,
        value=1,
    )

    return {
        "execution_arn": execution_arn,
        "game_date": game_date,
        "season": season,
    }
