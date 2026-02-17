"""Lambda handler for API authorizer — validate Cognito JWT tokens."""

import json
import os
from typing import Any
from urllib.request import urlopen

import jwt
from aws_lambda_powertools import Logger
from jwt.algorithms import RSAAlgorithm

logger = Logger()

COGNITO_USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
COGNITO_REGION = os.environ["COGNITO_REGION"]
COGNITO_CLIENT_IDS = os.environ["COGNITO_CLIENT_IDS"].split(",")

JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com" f"/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"

# Module-level cache for JWKS keys (persists across warm Lambda starts)
_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    """Fetch and cache JWKS from Cognito."""
    global _jwks_cache  # noqa: PLW0603
    if _jwks_cache is None:
        with urlopen(JWKS_URL) as response:
            _jwks_cache = json.loads(response.read())
    return _jwks_cache


def _get_public_key(token: str) -> Any:
    """Extract the public key matching the token's kid from JWKS."""
    headers = jwt.get_unverified_header(token)
    kid = headers["kid"]
    jwks = _get_jwks()

    for key in jwks["keys"]:
        if key["kid"] == kid:
            return RSAAlgorithm.from_jwk(key)

    raise jwt.InvalidTokenError(f"Public key not found for kid: {kid}")


def _generate_policy(principal_id: str, effect: str, resource: str) -> dict[str, Any]:
    """Generate an IAM policy document for API Gateway."""
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }


@logger.inject_lambda_context
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Validate a Bearer token and return an IAM policy document.

    Args:
        event: API Gateway TOKEN authorizer event with authorizationToken
            and methodArn.
        context: Lambda context (unused).

    Returns:
        IAM policy document allowing or denying invoke.
    """
    token_string = event.get("authorizationToken", "")
    method_arn = event["methodArn"]

    if not token_string.startswith("Bearer "):
        logger.warning("Auth denied — missing Bearer prefix")
        return _generate_policy("anonymous", "Deny", method_arn)

    token = token_string[7:]

    try:
        public_key = _get_public_key(token)
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=COGNITO_CLIENT_IDS,
        )
        principal_id = claims.get("sub", "unknown")
        logger.info("Auth allowed", extra={"principal": principal_id})
        return _generate_policy(principal_id, "Allow", method_arn)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        logger.warning("Auth denied — invalid token")
        return _generate_policy("anonymous", "Deny", method_arn)
