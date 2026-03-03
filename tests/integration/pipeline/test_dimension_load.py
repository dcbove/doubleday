"""Integration tests for the dimension load Lambda.

Loads dimension tables (teams, venues, games, umpires, players) from the MLB
API into silver Iceberg tables via a two-phase bronze cache + silver INSERT.

Tests are ordered by dependency: teams must load before venues (venues reads
the teams bronze cache for venue IDs). Umpires and players depend on
silver_pitches data existing for the test season.

Requires:
- Valid AWS credentials with permission to invoke Lambdas and query Athena
- Silver pitches data already loaded for season 2024 (for umpires/players)
- Deployed dev Lambdas and dimension table DDL (via terraform apply)

Run with: make test-integration
"""

import pytest

from tests.integration.pipeline.conftest import (
    GAME_DATE,
    SEASON,
    count_rows,
    invoke_lambda,
)

FUNCTION_NAME = "doubleday-dev-dimension-load"


@pytest.mark.integration
class TestDimensionLoadTeams:
    """Test teams dimension load — fetches from MLB API, loads silver_teams."""

    def test_loads_teams(self):
        """Load teams for the test season and verify rows are inserted."""
        result = invoke_lambda(
            FUNCTION_NAME,
            {"dimension": "teams", "season": SEASON},
        )

        assert result["dimension"] == "teams"
        assert result["season"] == SEASON
        assert result["records_loaded"] > 0

        row_count = count_rows("silver_teams", f"season = {SEASON}")
        assert row_count > 0


@pytest.mark.integration
class TestDimensionLoadVenues:
    """Test venues dimension load — reads teams bronze for venue IDs.

    Depends on teams bronze cache existing (run teams test first).
    """

    def test_loads_venues(self):
        """Load venues for the test season and verify rows are inserted."""
        # Ensure teams bronze exists (venues reads it for venue_ids)
        invoke_lambda(
            FUNCTION_NAME,
            {"dimension": "teams", "season": SEASON},
        )

        result = invoke_lambda(
            FUNCTION_NAME,
            {"dimension": "venues", "season": SEASON},
        )

        assert result["dimension"] == "venues"
        assert result["records_loaded"] > 0

        row_count = count_rows("silver_venues", f"season = {SEASON}")
        assert row_count > 0


@pytest.mark.integration
class TestDimensionLoadGames:
    """Test games dimension load — fetches schedule for a specific date."""

    def test_loads_games_for_date(self):
        """Load games for the test date and verify rows are inserted."""
        result = invoke_lambda(
            FUNCTION_NAME,
            {
                "dimension": "games",
                "season": SEASON,
                "game_dates": [GAME_DATE],
            },
        )

        assert result["dimension"] == "games"
        assert result["records_loaded"] > 0

        row_count = count_rows(
            "silver_games",
            f"season = {SEASON} AND official_date = '{GAME_DATE}'",
        )
        assert row_count > 0


@pytest.mark.integration
class TestDimensionLoadUmpires:
    """Test umpires dimension load — queries silver_games for umpire IDs.

    Uses date-scoped query (game_dates) to keep the test fast. Only umpires
    from the test date are discovered, but the full bronze cache is loaded
    into silver.

    Depends on silver_games data existing for the test date.
    """

    def test_loads_umpires(self):
        """Load umpires for the test date and verify rows are inserted."""
        # Umpires sources IDs from silver_games — verify games exist first
        games_count = count_rows(
            "silver_games",
            f"season = {SEASON} AND official_date = '{GAME_DATE}'",
        )
        assert games_count > 0, "silver_games must have data before loading umpires"

        result = invoke_lambda(
            FUNCTION_NAME,
            {"dimension": "umpires", "season": SEASON, "game_dates": [GAME_DATE]},
        )

        assert result["dimension"] == "umpires"
        assert result["records_loaded"] > 0

        row_count = count_rows("silver_umpires", f"season = {SEASON}")
        assert row_count > 0


@pytest.mark.integration
class TestDimensionLoadPlayers:
    """Test players dimension load — queries silver_pitches for player IDs.

    Uses date-scoped query (game_dates) to keep the test fast. Only players
    from the test date are discovered, but the full bronze cache is loaded
    into silver.

    Depends on silver_pitches data existing for the test date.
    """

    def test_loads_players(self):
        """Load players for the test date and verify rows are inserted."""
        result = invoke_lambda(
            FUNCTION_NAME,
            {"dimension": "players", "season": SEASON, "game_dates": [GAME_DATE]},
        )

        assert result["dimension"] == "players"
        assert result["records_loaded"] > 0

        row_count = count_rows("silver_players", f"season = {SEASON}")
        assert row_count > 0

    def test_reload_is_idempotent_and_cache_hits(self):
        """Reload players and verify row count is unchanged and cache is hit.

        The dimension load uses DELETE + INSERT, so reloading should produce
        the exact same row count (no duplicates). The second invocation should
        also report bronze_cached=True (no new IDs to fetch from the API).
        """
        payload = {"dimension": "players", "season": SEASON, "game_dates": [GAME_DATE]}

        first = invoke_lambda(FUNCTION_NAME, payload)
        second = invoke_lambda(FUNCTION_NAME, payload)

        assert second["records_loaded"] == first["records_loaded"]
        assert second["bronze_cached"] is True

        row_count = count_rows("silver_players", f"season = {SEASON}")
        assert row_count == first["records_loaded"]
