"""End-to-end auth integration tests for the query_pitches API.

These tests hit the real HTTPS endpoint with a real Cognito JWT and API key,
exercising the full auth flow: the authorizer Lambda validates the token, API
Gateway enforces the API key, and the request routes to the query Lambda.

For tests that bypass auth via ``test-invoke-method``, see
``test_query_pitches_gateway.py``.

Requires:
- A deployed API Gateway and authorizer in dev
- A test Cognito user and app client
- Credentials stored in Secrets Manager at
  ``dev/doubleday/cognito_identity_provider/integration_test_credentials``
"""

import functools
import json

import boto3
import pytest
import requests

_secrets_client = boto3.client("secretsmanager")

_secret = json.loads(
    _secrets_client.get_secret_value(
        SecretId="dev/doubleday/cognito_identity_provider/integration_test_credentials",
    )["SecretString"]
)

USER_POOL_ID = _secret["user_pool_id"]
TEST_CLIENT_ID = _secret["test_client_id"]
TEST_EMAIL = _secret["test_email"]
TEST_PASSWORD = _secret["test_password"]
API_KEY = _secret["api_key"]
API_URL = _secret["api_url"]

# Shohei Ohtani — guaranteed to have data if 2025 gold tables are loaded
PITCHER_ID = "660271"
SEASON = "2025"

# Sentinel to distinguish "use the default" from "omit the header"
_DEFAULT = object()


@functools.cache
def _authenticate() -> str:
    """Authenticate the test user and return an ID token.

    Uses Cognito USER_PASSWORD_AUTH flow against the test app client.
    The result is cached for the lifetime of the test session.

    Returns:
        A valid Cognito ID token string.
    """
    cognito_client = boto3.client("cognito-idp")
    response = cognito_client.initiate_auth(
        ClientId=TEST_CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": TEST_EMAIL,
            "PASSWORD": TEST_PASSWORD,
        },
    )
    return str(response["AuthenticationResult"]["IdToken"])


def _request(
    path: str,
    params: dict | None = None,
    token: object = _DEFAULT,
    api_key: object = _DEFAULT,
) -> requests.Response:
    """Send a GET request to the API with optional auth overrides.

    Args:
        path: The URL path (e.g. "/pitchers/660271/pitches").
        params: Optional query string parameters.
        token: Bearer token to send. ``_DEFAULT`` uses a valid token;
            ``None`` omits the Authorization header entirely.
        api_key: API key to send. ``_DEFAULT`` uses the real key;
            ``None`` omits the x-api-key header entirely.

    Returns:
        The raw ``requests.Response``.
    """
    headers: dict[str, str] = {}

    if token is _DEFAULT:
        headers["Authorization"] = f"Bearer {_authenticate()}"
    elif token is not None:
        headers["Authorization"] = f"Bearer {token}"

    if api_key is _DEFAULT:
        headers["x-api-key"] = API_KEY
    elif api_key is not None:
        headers["x-api-key"] = str(api_key)

    return requests.get(API_URL + path, params=params, headers=headers, timeout=30)


@pytest.mark.integration
class TestQueryPitchesAuth:
    """End-to-end auth tests for the query_pitches endpoint."""

    def test_valid_auth_returns_data(self):
        """Valid token + API key returns 200 with the expected response shape."""
        response = _request(
            f"/pitchers/{PITCHER_ID}/pitches",
            params={"season": SEASON},
        )

        assert response.status_code == 200

        body = response.json()
        assert body["pitcher"] == int(PITCHER_ID)
        assert body["season"] == int(SEASON)
        assert len(body["pitches"]) > 0

    def test_missing_token_returns_401(self):
        """Omitting the Authorization header returns 401."""
        response = _request(
            f"/pitchers/{PITCHER_ID}/pitches",
            params={"season": SEASON},
            token=None,
        )

        assert response.status_code == 401

    def test_invalid_token_returns_403(self):
        """A garbage Bearer token returns 403 (authorizer Deny policy)."""
        response = _request(
            f"/pitchers/{PITCHER_ID}/pitches",
            params={"season": SEASON},
            token="not-a-real-token",
        )

        assert response.status_code == 403

    def test_missing_api_key_returns_403(self):
        """Omitting the x-api-key header returns 403."""
        response = _request(
            f"/pitchers/{PITCHER_ID}/pitches",
            params={"season": SEASON},
            api_key=None,
        )

        assert response.status_code == 403
