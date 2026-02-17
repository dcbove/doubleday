"""Gateway integration tests for the query_pitches API.

These tests use ``apigateway:test-invoke-method`` to route requests through the
real API Gateway — resource matching, path parameter extraction, and integration
config are all exercised. The authorizer and API key check are skipped because
``test-invoke-method`` bypasses authentication.

For tests that invoke the Lambda directly with synthetic events, see
``test_query_pitches_synthetic.py``.

Requires valid AWS credentials, a deployed API Gateway in dev, and existing
gold table data for season 2025.
"""

import json
from typing import Any

import boto3
import pytest

apigw_client = boto3.client("apigateway")

API_NAME = "doubleday-dev-api"
RESOURCE_PATH = "/pitchers/{pitcher_id}/pitches"

# Shohei Ohtani — guaranteed to have data if 2025 gold tables are loaded
PITCHER_ID = "660271"
SEASON = "2025"


def _find_rest_api_id(name: str) -> str:
    """Find the REST API ID by name.

    Args:
        name: The name of the REST API to find.

    Returns:
        The REST API ID.

    Raises:
        ValueError: If no REST API with the given name is found.
    """
    paginator = apigw_client.get_paginator("get_rest_apis")
    for page in paginator.paginate():
        for item in page["items"]:
            if item["name"] == name:
                return str(item["id"])
    raise ValueError(f"REST API '{name}' not found")


def _find_resource_id(rest_api_id: str, path: str) -> str:
    """Find the resource ID for a given path in the REST API.

    Args:
        rest_api_id: The REST API ID to search within.
        path: The resource path to find (e.g. "/pitchers/{pitcher_id}/pitches").

    Returns:
        The resource ID.

    Raises:
        ValueError: If no resource with the given path is found.
    """
    paginator = apigw_client.get_paginator("get_resources")
    for page in paginator.paginate(restApiId=rest_api_id):
        for item in page["items"]:
            if item["path"] == path:
                return str(item["id"])
    raise ValueError(f"Resource '{path}' not found in API '{rest_api_id}'")


REST_API_ID = _find_rest_api_id(API_NAME)
RESOURCE_ID = _find_resource_id(REST_API_ID, RESOURCE_PATH)


def _invoke(path_with_query_string: str) -> dict[str, Any]:
    """Invoke the API Gateway test method and return the parsed response.

    Calls ``test-invoke-method`` which routes the request through the real API
    Gateway resource matching and integration config, but skips the authorizer.

    Args:
        path_with_query_string: The full path including query string
            (e.g. "/pitchers/660271/pitches?season=2025").

    Returns:
        A dict with "status" (int) and "body" (parsed JSON dict).
    """
    response = apigw_client.test_invoke_method(
        restApiId=REST_API_ID,
        resourceId=RESOURCE_ID,
        httpMethod="GET",
        pathWithQueryString=path_with_query_string,
    )

    body = json.loads(response["body"]) if response["body"] else {}
    return {"status": response["status"], "body": body}


@pytest.mark.integration
class TestQueryPitchesGateway:
    """Test the query_pitches API through API Gateway test-invoke-method."""

    def test_returns_pitch_data(self):
        """Query a known pitcher/season and verify the response shape.

        Sends a valid request for Shohei Ohtani's 2025 season and asserts:
        - 200 status code
        - Response body contains the correct pitcher and season
        - At least one pitch type is returned
        - Each pitch type has expected numeric fields
        """
        response = _invoke(f"/pitchers/{PITCHER_ID}/pitches?season={SEASON}")

        assert response["status"] == 200

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
        response = _invoke(f"/pitchers/{PITCHER_ID}/pitches?season={SEASON}&pitch_type=ST")

        assert response["status"] == 200

        pitches = response["body"]["pitches"]
        assert len(pitches) == 1
        assert pitches[0]["pitch_type"] == "ST"

    def test_missing_season_returns_400(self):
        """Omit the required season parameter and verify a 400 response."""
        response = _invoke(f"/pitchers/{PITCHER_ID}/pitches")

        assert response["status"] == 400
        assert "season" in response["body"]["error"].lower()

    def test_missing_pitcher_id_returns_400(self):
        """Omit the pitcher_id path parameter and verify a 400 response.

        Uses the resource path template directly — API Gateway will pass
        the literal ``{pitcher_id}`` string as the path parameter value,
        which the handler should reject.
        """
        response = _invoke("/pitchers//pitches?season=" + SEASON)

        assert response["status"] == 400
        assert "pitcher_id" in response["body"]["error"].lower()

    def test_nonexistent_pitcher_returns_empty(self):
        """Query a pitcher with no data and verify an empty pitches list."""
        response = _invoke(f"/pitchers/9999999/pitches?season={SEASON}")

        assert response["status"] == 200
        assert response["body"]["pitches"] == []
