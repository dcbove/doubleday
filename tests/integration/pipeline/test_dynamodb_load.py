"""Integration tests for the DynamoDB load Lambda.

Loads gold data into the DynamoDB serving table. Tests are ordered by
dependency: pitches and neighbors depend on gold tables already being
populated, and catalog depends on gold_catalog.

Requires:
- Valid AWS credentials with permission to invoke Lambdas
- Gold data already loaded for the test season (run the pipeline first)
- Deployed dev Lambdas (via terraform apply in the dev environment)

Run with: make test-integration
"""

import pytest

from tests.integration.pipeline.conftest import SEASON, invoke_lambda


@pytest.mark.integration
class TestDynamoDBLoad:
    """Test the DynamoDB load Lambda — replicates gold data to DynamoDB."""

    def test_loads_pitches(self):
        """Load pitches entity and verify items are written."""
        result = invoke_lambda(
            "doubleday-dev-dynamodb-load",
            {
                "entity_type": "pitches",
                "season": SEASON,
            },
        )

        assert result["records_loaded"] > 0
        assert result["entity_type"] == "pitches"

    def test_loads_neighbors(self):
        """Load neighbors entity and verify items are written."""
        result = invoke_lambda(
            "doubleday-dev-dynamodb-load",
            {
                "entity_type": "neighbors",
                "season": SEASON,
            },
        )

        assert result["records_loaded"] > 0
        assert result["entity_type"] == "neighbors"

    def test_loads_catalog(self):
        """Load catalog entity and verify items are written."""
        result = invoke_lambda(
            "doubleday-dev-dynamodb-load",
            {
                "entity_type": "catalog",
                "season": SEASON,
            },
        )

        assert result["records_loaded"] > 0
        assert result["entity_type"] == "catalog"
