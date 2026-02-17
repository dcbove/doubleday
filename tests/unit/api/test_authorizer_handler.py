"""Unit tests for the API Gateway custom authorizer (doubleday.api.authorizer.handler).

The authorizer is a TOKEN-type Lambda that validates Cognito JWT tokens on
every API request. It receives a Bearer token from the Authorization header,
verifies the signature against the Cognito JWKS endpoint, and returns an IAM
policy document that either Allows or Denies the request.

These tests mock the JWT library and JWKS key retrieval to test the handler's
branching logic: valid tokens, expired tokens, malformed tokens, and missing
tokens. Environment variables (COGNITO_USER_POOL_ID, COGNITO_REGION,
COGNITO_CLIENT_IDS) are set before import because the handler reads them at
module level.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before importing handler (module-level os.environ reads)
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_TestPool")
os.environ.setdefault("COGNITO_REGION", "us-east-1")
os.environ.setdefault("COGNITO_CLIENT_IDS", "test-client-id")

from doubleday.api.authorizer.handler import handler  # noqa: E402

METHOD_ARN = "arn:aws:execute-api:us-east-1:123456:api/dev/GET/pitchers"


@pytest.fixture()
def lambda_context():
    """Create a mock Lambda context for Powertools inject_lambda_context."""
    ctx = MagicMock()
    ctx.function_name = "test-authorizer"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456:function:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


class TestAuthorizerHandler:
    """Tests for the authorizer handler's Allow/Deny decisions.

    Each test constructs a TOKEN authorizer event (with authorizationToken and
    methodArn) and asserts the returned IAM policy document has the correct
    Effect (Allow or Deny) and principalId.
    """

    @patch("doubleday.api.authorizer.handler._get_public_key")
    @patch("doubleday.api.authorizer.handler.jwt")
    def test_valid_id_token_returns_allow(self, mock_jwt, mock_get_key, lambda_context):
        """Valid id token returns Allow policy with user's sub as principalId."""
        mock_get_key.return_value = MagicMock()
        mock_jwt.decode.return_value = {
            "sub": "user-123",
            "token_use": "id",
            "aud": "test-client-id",
        }
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidTokenError = Exception

        event = {
            "authorizationToken": "Bearer valid-token",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "user-123"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Allow"
        assert statement["Resource"] == METHOD_ARN

    @patch("doubleday.api.authorizer.handler._get_public_key")
    @patch("doubleday.api.authorizer.handler.jwt")
    def test_valid_access_token_returns_allow(self, mock_jwt, mock_get_key, lambda_context):
        """Valid access token returns Allow policy with user's sub as principalId."""
        mock_get_key.return_value = MagicMock()
        mock_jwt.decode.return_value = {
            "sub": "user-123",
            "token_use": "access",
            "client_id": "test-client-id",
        }
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidTokenError = Exception

        event = {
            "authorizationToken": "Bearer valid-access-token",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "user-123"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Allow"

    @patch("doubleday.api.authorizer.handler._get_public_key")
    @patch("doubleday.api.authorizer.handler.jwt")
    def test_wrong_client_id_returns_deny(self, mock_jwt, mock_get_key, lambda_context):
        """Token with unrecognized client ID returns Deny policy."""
        mock_get_key.return_value = MagicMock()
        invalid_error = type("InvalidTokenError", (Exception,), {})
        mock_jwt.decode.return_value = {
            "sub": "user-123",
            "token_use": "access",
            "client_id": "wrong-client-id",
        }
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidTokenError = invalid_error

        event = {
            "authorizationToken": "Bearer valid-token-wrong-client",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "anonymous"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Deny"

    @patch("doubleday.api.authorizer.handler._get_public_key")
    @patch("doubleday.api.authorizer.handler.jwt")
    def test_expired_token_returns_deny(self, mock_jwt, mock_get_key, lambda_context):
        """Expired token returns Deny policy."""
        mock_get_key.return_value = MagicMock()
        expired_error = type("ExpiredSignatureError", (Exception,), {})
        mock_jwt.ExpiredSignatureError = expired_error
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.decode.side_effect = expired_error("Token expired")

        event = {
            "authorizationToken": "Bearer expired-token",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "anonymous"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Deny"

    @patch("doubleday.api.authorizer.handler._get_public_key")
    @patch("doubleday.api.authorizer.handler.jwt")
    def test_malformed_token_returns_deny(self, mock_jwt, mock_get_key, lambda_context):
        """Malformed token returns Deny policy."""
        invalid_error = type("InvalidTokenError", (Exception,), {})
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidTokenError = invalid_error
        mock_get_key.side_effect = invalid_error("Bad token")

        event = {
            "authorizationToken": "Bearer bad-token",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "anonymous"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Deny"

    def test_missing_token_returns_deny(self, lambda_context):
        """Missing Bearer prefix returns Deny policy."""
        event = {
            "authorizationToken": "",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "anonymous"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Deny"

    def test_non_bearer_token_returns_deny(self, lambda_context):
        """Non-Bearer token returns Deny policy."""
        event = {
            "authorizationToken": "Basic dXNlcjpwYXNz",
            "methodArn": METHOD_ARN,
        }

        result = handler(event, lambda_context)

        assert result["principalId"] == "anonymous"
        statement = result["policyDocument"]["Statement"][0]
        assert statement["Effect"] == "Deny"
