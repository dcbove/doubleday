"""Integration tests for the gold load Lambda.

Rebuilds gold aggregate tables from silver data. Tests are ordered by dependency:
shape_season must be loaded before norm_stats, and norm_stats before neighbors.

Requires:
- Valid AWS credentials with permission to invoke Lambdas
- Silver data already loaded for the test season (run the pipeline first)
- Deployed dev Lambdas (via terraform apply in the dev environment)

Run with: make test-integration
"""

import pytest

from tests.integration.pipeline.conftest import SEASON, invoke_lambda


@pytest.mark.integration
class TestGoldLoad:
    """Test the gold load Lambda — rebuilds gold aggregate tables from silver."""

    def test_loads_shape_season(self):
        """Load the gold_pitches_shape_season table and verify rows are inserted."""
        result = invoke_lambda(
            "doubleday-dev-gold-load",
            {
                "table_name": "gold_pitches_shape_season",
                "season": SEASON,
            },
        )

        assert result["records_inserted"] > 0
        assert result["table_name"] == "gold_pitches_shape_season"

    def test_loads_norm_stats(self):
        """Load the gold_pitch_type_norm_stats table and verify rows are inserted.

        Depends on gold_pitches_shape_season data being present.
        """
        result = invoke_lambda(
            "doubleday-dev-gold-load",
            {
                "table_name": "gold_pitch_type_norm_stats",
                "season": SEASON,
            },
        )

        assert result["records_inserted"] > 0
        assert result["table_name"] == "gold_pitch_type_norm_stats"

    def test_loads_neighbors(self):
        """Load the gold_repertoire_shape_neighbors table and verify rows are inserted.

        Depends on gold_pitch_type_norm_stats data being present. Uses
        format_params to pass lambda/tau hyperparameters to the SQL template.
        """
        result = invoke_lambda(
            "doubleday-dev-gold-load",
            {
                "table_name": "gold_repertoire_shape_neighbors",
                "season": SEASON,
                "format_params": {
                    "lambda": "0.4",
                    "tau": "1",
                },
            },
        )

        assert result["records_inserted"] > 0
        assert result["table_name"] == "gold_repertoire_shape_neighbors"

    def test_loads_catalog(self):
        """Load the gold_catalog table and verify rows are inserted.

        Depends on silver_pitches, silver_players, and silver_teams data
        being present for the test season.
        """
        result = invoke_lambda(
            "doubleday-dev-gold-load",
            {
                "table_name": "gold_catalog",
                "season": SEASON,
            },
        )

        assert result["records_inserted"] > 0
        assert result["table_name"] == "gold_catalog"
