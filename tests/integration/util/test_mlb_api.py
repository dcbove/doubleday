"""Integration tests for MLB Stats API client — calls the real API.

These tests verify that the MLB API response format matches our parsing
logic. They require network access and should NOT be run in CI — only
locally when validating API assumptions.

Run with: uv run pytest tests/integration/util/test_mlb_api.py -v
"""

from doubleday.util.mlb import (
    GameInfo,
    PlayerEnrichment,
    TeamDetail,
    TeamInfo,
    UmpireInfo,
    VenueInfo,
    fetch_players,
    fetch_schedule,
    fetch_teams,
    fetch_teams_for_season,
    fetch_umpires,
    fetch_venues,
)


class TestFetchTeamsLive:
    """Live API tests for fetch_teams."""

    def test_returns_teams_keyed_by_abbreviation(self):
        """Should return ~30 teams keyed by abbreviation."""
        teams = fetch_teams()

        assert len(teams) >= 29
        assert all(isinstance(v, TeamInfo) for v in teams.values())
        assert all(isinstance(k, str) and len(k) <= 3 for k in teams)

    def test_known_team_fields(self):
        """Spot-check Yankees fields are parsed correctly."""
        teams = fetch_teams()

        assert "NYY" in teams
        nyy = teams["NYY"]
        assert nyy.team_id == 147
        assert nyy.team_name == "Yankees"


class TestFetchPlayersLive:
    """Live API tests for fetch_players."""

    def test_known_player(self):
        """Fetches a known player with all enrichment fields."""
        # 592450 = Aaron Judge
        result = fetch_players([592450])

        assert 592450 in result
        player = result[592450]
        assert isinstance(player, PlayerEnrichment)
        assert player.player_id == 592450
        assert player.first_name == "Aaron"
        assert player.last_name == "Judge"
        assert player.bats in ("L", "R", "S")
        assert player.throws in ("L", "R")
        assert player.position != ""
        # current_team_id may be None during offseason/spring training/DFA
        assert player.current_team_id is None or isinstance(player.current_team_id, int)
        assert "592450" in player.headshot_url

    def test_multiple_players(self):
        """Fetches multiple players in one call."""
        # 592450 = Judge, 605151 = Gerrit Cole
        result = fetch_players([592450, 605151])

        assert len(result) == 2
        assert 592450 in result
        assert 605151 in result

    def test_retired_player_has_no_current_team(self):
        """A retired player may have no currentTeam."""
        # 120074 = Babe Ruth
        result = fetch_players([120074])

        assert 120074 in result
        player = result[120074]
        assert player.first_name != ""
        assert player.current_team_id is None


class TestFetchTeamsForSeasonLive:
    """Live API tests for fetch_teams_for_season."""

    def test_returns_teams_for_2024(self):
        """2024 season should return ~30 teams with expected fields."""
        teams = fetch_teams_for_season(2024)

        assert len(teams) >= 29
        assert all(isinstance(t, TeamDetail) for t in teams)

        # Spot-check a well-known team
        nyy = next((t for t in teams if t.abbreviation == "NYY"), None)
        assert nyy is not None
        assert nyy.team_id == 147
        assert nyy.team_name == "Yankees"
        assert nyy.full_name == "New York Yankees"
        assert nyy.league_id is not None
        assert nyy.league_name != ""
        assert nyy.division_id is not None
        assert nyy.division_name != ""
        assert nyy.venue_id is not None
        assert nyy.active is True

    def test_all_teams_have_venue_ids(self):
        """Every active team should have a venue_id for the venues dimension."""
        teams = fetch_teams_for_season(2024)
        active_teams = [t for t in teams if t.active]

        for team in active_teams:
            assert team.venue_id is not None, f"{team.abbreviation} has no venue_id"


class TestFetchVenuesLive:
    """Live API tests for fetch_venues."""

    def test_fetches_yankee_stadium(self):
        """Yankee Stadium (3313) should return full location data."""
        venues = fetch_venues([3313])

        assert len(venues) == 1
        venue = venues[0]
        assert isinstance(venue, VenueInfo)
        assert venue.venue_id == 3313
        assert venue.name == "Yankee Stadium"
        assert venue.city == "Bronx"
        assert venue.state_abbrev == "NY"
        assert venue.latitude is not None
        assert venue.longitude is not None
        assert venue.country != ""

    def test_fetches_multiple_venues(self):
        """Multiple venue IDs each return a result."""
        # 3313 = Yankee Stadium, 15 = Chase Field
        venues = fetch_venues([3313, 15])

        assert len(venues) == 2
        venue_ids = {v.venue_id for v in venues}
        assert venue_ids == {3313, 15}

    def test_all_2024_team_venues_fetchable(self):
        """Every venue_id from the 2024 teams should be fetchable."""
        teams = fetch_teams_for_season(2024)
        venue_ids = list({t.venue_id for t in teams if t.venue_id is not None})

        venues = fetch_venues(venue_ids)

        fetched_ids = {v.venue_id for v in venues}
        missing = set(venue_ids) - fetched_ids
        assert not missing, f"Failed to fetch venues: {missing}"


class TestFetchScheduleLive:
    """Live API tests for fetch_schedule."""

    def test_regular_season_date(self):
        """A known regular season date should return multiple games."""
        # June 15, 2024 — a mid-season Sunday with a full slate
        games = fetch_schedule("2024-06-15")

        assert len(games) >= 5
        assert all(isinstance(g, GameInfo) for g in games)

        for game in games:
            assert game.game_pk > 0
            assert game.season == 2024
            assert game.official_date.startswith("2024-06-")
            assert game.away_team_id > 0
            assert game.home_team_id > 0
            assert game.venue_id is not None

    def test_completed_games_have_scores(self):
        """Completed games should have non-None scores."""
        games = fetch_schedule("2024-06-15")

        games_with_scores = [g for g in games if g.home_score is not None]
        assert len(games_with_scores) > 0

        for game in games_with_scores:
            assert game.away_score is not None
            assert isinstance(game.home_score, int)
            assert isinstance(game.away_score, int)

    def test_hp_umpire_present_on_completed_games(self):
        """Most completed games should have a home plate umpire assigned."""
        games = fetch_schedule("2024-06-15")

        games_with_umpire = [g for g in games if g.hp_umpire_id is not None]
        # Most games should have an HP umpire; allow a few to be missing
        assert (
            len(games_with_umpire) >= len(games) // 2
        ), f"Only {len(games_with_umpire)}/{len(games)} games had HP umpire"

        for game in games_with_umpire:
            assert game.hp_umpire_id > 0
            assert game.hp_umpire_name != ""

    def test_off_day_returns_empty(self):
        """A date with no games returns an empty list."""
        # Christmas Day 2024 — no MLB games
        games = fetch_schedule("2024-12-25")

        assert games == []


class TestFetchUmpiresLive:
    """Live API tests for fetch_umpires."""

    def test_known_umpire(self):
        """Fetches a known umpire by ID."""
        # 427542 = Angel Hernandez (retired but still in the system)
        result = fetch_umpires([427542])

        assert 427542 in result
        umpire = result[427542]
        assert isinstance(umpire, UmpireInfo)
        assert umpire.umpire_id == 427542
        assert umpire.full_name != ""

    def test_umpires_from_schedule(self):
        """Umpire IDs extracted from the schedule should all be fetchable."""
        games = fetch_schedule("2024-06-15")
        umpire_ids = [g.hp_umpire_id for g in games if g.hp_umpire_id is not None]

        assert len(umpire_ids) > 0, "No HP umpires found in schedule"

        result = fetch_umpires(umpire_ids)

        for uid in umpire_ids:
            assert uid in result, f"Umpire {uid} not found in API response"
            assert result[uid].full_name != ""
