"""Synthetic integration tests for the query_pitches API Lambda.

These tests invoke the deployed Lambda directly with synthetic API Gateway
proxy events — the same JSON structure that API Gateway sends on a real
request, but constructed in the test. This bypasses API Gateway entirely
(no resource matching, no integration config, no authorizer) and tests the
handler's event parsing and Athena query logic against real data in the dev
environment.

For tests that route through the real API Gateway, see
``test_query_pitches_gateway.py``.

Requires valid AWS credentials and existing gold table data for season 2025.
"""

import json
from typing import Any

import boto3
import pytest

lambda_client = boto3.client("lambda")

FUNCTION_NAME = "doubleday-dev-api-query-pitches"

# Shohei Ohtani — guaranteed to have data if 2025 gold tables are loaded
PITCHER_ID = "660271"
SEASON = "2025"


def _apigw_event(
    path_params: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway proxy integration event.

    API Gateway sends this structure to Lambda when using proxy integration.
    Only the fields that the handler actually reads are included.

    Args:
        path_params: Path parameters (e.g. {"pitcher_id": "660271"}).
        query_params: Query string parameters (e.g. {"season": "2024"}).

    Returns:
        A dict matching the API Gateway proxy event shape.
    """
    return {
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "httpMethod": "GET",
        "resource": "/pitchers/{pitcher_id}/pitches",
    }


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the query_pitches Lambda and return its response.

    The Lambda returns an API Gateway proxy response with statusCode, headers,
    and a JSON-encoded body. This helper parses the body and returns the full
    response dict with the body already decoded.

    Args:
        event: API Gateway proxy event to send as the Lambda payload.

    Returns:
        The Lambda response with 'body' parsed from JSON string to dict.
    """
    response = lambda_client.invoke(
        FunctionName=FUNCTION_NAME,
        Payload=json.dumps(event),
    )

    if "FunctionError" in response:
        raw = json.loads(response["Payload"].read())
        pytest.fail(f"{FUNCTION_NAME} raised an error: {raw}")

    result: dict[str, Any] = json.loads(response["Payload"].read())
    result["body"] = json.loads(result["body"])
    return result


@pytest.mark.integration
class TestQueryPitchesSynthetic:
    """Test the query_pitches Lambda with synthetic API Gateway events."""

    def test_returns_pitch_data(self):
        """Query a known pitcher/season and verify the response shape.

        Sends a valid request for Shohei Ohtani's 2025 season and asserts:
        - 200 status code
        - Response body contains the correct pitcher and season
        - At least one pitch type is returned
        - Each pitch type has expected numeric fields
        """
        event = _apigw_event(
            path_params={"pitcher_id": PITCHER_ID},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200

        body = response["body"]
        assert body["pitcher"] == int(PITCHER_ID)
        assert body["season"] == int(SEASON)
        assert len(body["pitches"]) > 0

        pitch = body["pitches"][0]
        assert "pitch_type" in pitch
        assert isinstance(pitch["avg_velocity"], float)
        assert isinstance(pitch["pitch_count"], int)

    def test_filters_by_pitch_type(self):
        """Query with a pitch_type filter and verify only that type is returned.

        Ohtani throws a sweeper (ST). The response should contain exactly one
        pitch type entry matching the filter.
        """
        event = _apigw_event(
            path_params={"pitcher_id": PITCHER_ID},
            query_params={"season": SEASON, "pitch_type": "ST"},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200

        pitches = response["body"]["pitches"]
        assert len(pitches) == 1
        assert pitches[0]["pitch_type"] == "ST"

    def test_missing_season_returns_400(self):
        """Omit the required season parameter and verify a 400 response."""
        event = _apigw_event(
            path_params={"pitcher_id": PITCHER_ID},
            query_params=None,
        )
        response = _invoke(event)

        assert response["statusCode"] == 400
        assert "season" in response["body"]["error"].lower()

    def test_missing_pitcher_id_returns_400(self):
        """Omit the pitcher_id path parameter and verify a 400 response."""
        event = _apigw_event(
            path_params=None,
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 400
        assert "pitcher_id" in response["body"]["error"].lower()

    def test_nonexistent_pitcher_returns_empty(self):
        """Query a pitcher with no data and verify an empty pitches list."""
        event = _apigw_event(
            path_params={"pitcher_id": "9999999"},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200
        assert response["body"]["pitches"] == []
