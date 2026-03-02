"""Synthetic integration tests for the catalog API Lambda.

These tests invoke the deployed Lambda directly with synthetic API Gateway
proxy events. This bypasses API Gateway entirely (no authorizer, no routing)
and tests the handler's event parsing and DynamoDB query logic against real
data in the dev environment.

The catalog endpoint does not require a subscription — it is free for all
authenticated users. The principalId is included in the event because the
handler still receives it from API Gateway, but no entitlement check occurs.

Requires valid AWS credentials, a deployed catalog Lambda in dev, and
catalog data loaded into the DynamoDB serving table for season 2024.

Run with: make test-integration
"""

import json
from typing import Any

import boto3
import pytest

lambda_client = boto3.client("lambda")

FUNCTION_NAME = "doubleday-dev-api-catalog"
SEASON = "2024"


def _apigw_event(
    path_params: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway proxy integration event.

    Args:
        path_params: Path parameters (e.g. {"role": "pitchers"}).
        query_params: Query string parameters (e.g. {"season": "2024"}).

    Returns:
        A dict matching the API Gateway proxy event shape.
    """
    return {
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "httpMethod": "GET",
        "resource": "/catalogs/{role}",
        "requestContext": {
            "authorizer": {
                "principalId": "integration-test",
            },
        },
    }


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the catalog Lambda and return its response.

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
class TestCatalogSynthetic:
    """Test the catalog Lambda with synthetic API Gateway events."""

    def test_returns_pitchers_catalog(self):
        """Query the pitchers catalog and verify the response shape."""
        event = _apigw_event(
            path_params={"role": "pitchers"},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200

        body = response["body"]
        assert body["season"] == int(SEASON)
        assert body["role"] == "pitchers"
        assert len(body["players"]) > 0

        player = body["players"][0]
        assert "player_id" in player
        assert "first_name" in player
        assert "last_name" in player

    def test_returns_batters_catalog(self):
        """Query the batters catalog and verify it returns players."""
        event = _apigw_event(
            path_params={"role": "batters"},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200
        assert len(response["body"]["players"]) > 0

    def test_players_sorted_by_last_name(self):
        """Verify players are sorted alphabetically by last name."""
        event = _apigw_event(
            path_params={"role": "pitchers"},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        players = response["body"]["players"]
        last_names = [p["last_name"] for p in players]
        assert last_names == sorted(last_names)

    def test_invalid_role_returns_400(self):
        """Request with an invalid role returns 400."""
        event = _apigw_event(
            path_params={"role": "catchers"},
            query_params={"season": SEASON},
        )
        response = _invoke(event)

        assert response["statusCode"] == 400
        assert "role" in response["body"]["error"].lower()

    def test_missing_season_returns_400(self):
        """Omit the required season parameter and verify a 400 response."""
        event = _apigw_event(
            path_params={"role": "pitchers"},
            query_params=None,
        )
        response = _invoke(event)

        assert response["statusCode"] == 400
        assert "season" in response["body"]["error"].lower()

    def test_nonexistent_season_returns_empty(self):
        """Query a season with no data and verify an empty players list."""
        event = _apigw_event(
            path_params={"role": "pitchers"},
            query_params={"season": "1900"},
        )
        response = _invoke(event)

        assert response["statusCode"] == 200
        assert response["body"]["players"] == []
