"""Shared fixtures for API integration tests.

Seeds an active entitlement record for the integration test user so that
subscription-gated endpoints return 200 instead of 403.
"""

import json

import boto3
import jwt
import pytest

_secrets_client = boto3.client("secretsmanager")
_dynamodb = boto3.resource("dynamodb")

_secret = json.loads(
    _secrets_client.get_secret_value(
        SecretId="dev/doubleday/cognito_identity_provider/integration_test_credentials",
    )["SecretString"]
)

TEST_CLIENT_ID = _secret["test_client_id"]
TEST_EMAIL = _secret["test_email"]
TEST_PASSWORD = _secret["test_password"]

ENTITLEMENTS_TABLE = "doubleday-dev-entitlements"


def _get_test_user_sub() -> str:
    """Authenticate the test user and extract the cognito sub from the ID token.

    Returns:
        The test user's Cognito sub claim.
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
    id_token = response["AuthenticationResult"]["IdToken"]
    claims = jwt.decode(id_token, options={"verify_signature": False})
    return str(claims["sub"])


_test_user_sub: str | None = None


@pytest.fixture(scope="session", autouse=True)
def seed_test_entitlement():
    """Ensure the integration test user has an active entitlement."""
    global _test_user_sub  # noqa: PLW0603
    _test_user_sub = _get_test_user_sub()
    table = _dynamodb.Table(ENTITLEMENTS_TABLE)

    table.put_item(
        Item={
            "PK": f"USER#{_test_user_sub}",
            "status": "active",
            "tier": "basic",
            "email": TEST_EMAIL,
        },
    )

    yield

    table.delete_item(Key={"PK": f"USER#{_test_user_sub}"})


@pytest.fixture(scope="session")
def test_user_sub(seed_test_entitlement):
    """Return the test user's Cognito sub (available after entitlement is seeded)."""
    return _test_user_sub
