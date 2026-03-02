"""Unit tests for the MLB Stats API client (doubleday.util.mlb).

This module provides functions for fetching player enrichment data, team
metadata, venue metadata, game schedules, and umpire metadata from the MLB
Stats API. It batches player and umpire requests (200 per call), handles
partial failures gracefully, and normalizes player names for search.

These tests mock urllib.urlopen to verify: team parsing, player enrichment
extraction, batching logic, partial failure handling, empty input, name
normalization, venue fetching, schedule parsing, and umpire fetching.
"""

from unittest.mock import MagicMock, patch

import pytest

from doubleday.util.mlb import (
    BATCH_SIZE,
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
    normalize_name,
)


def _mock_urlopen_response(data: dict) -> MagicMock:
    """Create a mock urlopen response that returns JSON data."""
    import json

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestFetchTeams:
    """Tests for fetch_teams — fetches all MLB teams keyed by abbreviation."""

    @patch("doubleday.util.mlb.urlopen")
    def test_parses_team_response(self, mock_urlopen):
        """Returns TeamInfo dict keyed by abbreviation."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "teams": [
                    {
                        "id": 147,
                        "abbreviation": "NYY",
                        "teamName": "Yankees",
                    },
                    {
                        "id": 121,
                        "abbreviation": "NYM",
                        "teamName": "Mets",
                    },
                ]
            }
        )

        result = fetch_teams()

        assert len(result) == 2
        assert isinstance(result["NYY"], TeamInfo)
        assert result["NYY"].team_id == 147
        assert result["NYY"].abbreviation == "NYY"
        assert result["NYY"].team_name == "Yankees"
        assert result["NYM"].team_id == 121

    @patch("doubleday.util.mlb.urlopen")
    def test_skips_teams_without_abbreviation(self, mock_urlopen):
        """Teams missing abbreviation are excluded."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "teams": [
                    {"id": 147, "abbreviation": "NYY", "teamName": "Yankees"},
                    {"id": 999, "abbreviation": "", "teamName": "Unknown"},
                ]
            }
        )

        result = fetch_teams()

        assert len(result) == 1
        assert "NYY" in result

    @patch("doubleday.util.mlb.urlopen")
    def test_empty_teams_response(self, mock_urlopen):
        """Empty teams list returns empty dict."""
        mock_urlopen.return_value = _mock_urlopen_response({"teams": []})

        result = fetch_teams()

        assert result == {}


class TestFetchPlayers:
    """Tests for fetch_players — batch-fetches player enrichment from MLB API."""

    @patch("doubleday.util.mlb.urlopen")
    def test_single_player(self, mock_urlopen):
        """Fetches and parses a single player correctly."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "people": [
                    {
                        "id": 605151,
                        "firstName": "Gerrit",
                        "lastName": "Cole",
                        "batSide": {"code": "R"},
                        "pitchHand": {"code": "R"},
                        "primaryPosition": {"abbreviation": "P"},
                        "currentTeam": {"id": 147},
                    }
                ]
            }
        )

        result = fetch_players([605151])

        assert len(result) == 1
        player = result[605151]
        assert isinstance(player, PlayerEnrichment)
        assert player.first_name == "Gerrit"
        assert player.last_name == "Cole"
        assert player.bats == "R"
        assert player.throws == "R"
        assert player.position == "P"
        assert player.current_team_id == 147
        assert "605151" in player.headshot_url

    @patch("doubleday.util.mlb.urlopen")
    def test_batches_large_requests(self, mock_urlopen):
        """Requests with more than BATCH_SIZE IDs are split into batches."""
        total_ids = BATCH_SIZE + 50
        player_ids = list(range(1, total_ids + 1))

        def make_response(req):
            # Parse IDs from the URL
            url = req.full_url if hasattr(req, "full_url") else str(req)
            ids_param = url.split("personIds=")[1]
            ids = [int(x) for x in ids_param.split(",")]
            return _mock_urlopen_response(
                {
                    "people": [
                        {
                            "id": pid,
                            "firstName": "F",
                            "lastName": "L",
                            "batSide": {"code": "R"},
                            "pitchHand": {"code": "R"},
                            "primaryPosition": {"abbreviation": "P"},
                            "currentTeam": {"id": 1},
                        }
                        for pid in ids
                    ]
                }
            )

        mock_urlopen.side_effect = make_response

        result = fetch_players(player_ids)

        assert len(result) == total_ids
        assert mock_urlopen.call_count == 2

    @patch("doubleday.util.mlb.urlopen")
    def test_partial_batch_failure(self, mock_urlopen):
        """If one batch fails, results from successful batches are still returned."""
        total_ids = BATCH_SIZE + 50
        player_ids = list(range(1, total_ids + 1))

        first_batch_resp = _mock_urlopen_response(
            {
                "people": [
                    {
                        "id": pid,
                        "firstName": "F",
                        "lastName": "L",
                        "batSide": {"code": "R"},
                        "pitchHand": {"code": "R"},
                        "primaryPosition": {"abbreviation": "P"},
                        "currentTeam": {"id": 1},
                    }
                    for pid in range(1, BATCH_SIZE + 1)
                ]
            }
        )

        mock_urlopen.side_effect = [first_batch_resp, Exception("API error")]

        result = fetch_players(player_ids)

        assert len(result) == BATCH_SIZE

    def test_empty_input_returns_empty_dict(self):
        """Empty player ID list returns empty dict without API calls."""
        result = fetch_players([])

        assert result == {}

    @patch("doubleday.util.mlb.urlopen")
    def test_missing_optional_fields(self, mock_urlopen):
        """Player with missing optional fields gets safe defaults."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "people": [
                    {
                        "id": 12345,
                    }
                ]
            }
        )

        result = fetch_players([12345])

        player = result[12345]
        assert player.first_name == ""
        assert player.last_name == ""
        assert player.bats == ""
        assert player.throws == ""
        assert player.position == ""
        assert player.current_team_id is None


class TestNormalizeName:
    """Tests for normalize_name — strips diacritics and non-alphanumeric chars."""

    def test_simple_lowercase(self):
        """Converts simple name to lowercase."""
        assert normalize_name("Cole") == "cole"

    def test_diacritics_stripped(self):
        """Strips accented characters to their base form."""
        assert normalize_name("Ramírez") == "ramirez"

    def test_apostrophe_removed(self):
        """Removes apostrophes."""
        assert normalize_name("O'Brien") == "obrien"

    def test_hyphen_removed(self):
        """Removes hyphens."""
        assert normalize_name("De La Cruz") == "delacruz"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_name("") == ""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("González", "gonzalez"),
            ("Hernández", "hernandez"),
            ("Señor Jr.", "senorjr"),
        ],
    )
    def test_various_diacritics(self, raw, expected):
        """Various diacritics are normalized correctly."""
        assert normalize_name(raw) == expected


class TestFetchTeamsForSeason:
    """Tests for fetch_teams_for_season — fetches extended team metadata."""

    @patch("doubleday.util.mlb.urlopen")
    def test_parses_full_team_detail(self, mock_urlopen):
        """Parses all TeamDetail fields from API response."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "teams": [
                    {
                        "id": 147,
                        "abbreviation": "NYY",
                        "teamName": "Yankees",
                        "name": "New York Yankees",
                        "league": {"id": 103, "name": "American League"},
                        "division": {"id": 201, "name": "American League East"},
                        "venue": {"id": 3313},
                        "active": True,
                    }
                ]
            }
        )

        result = fetch_teams_for_season(2025)

        assert len(result) == 1
        team = result[0]
        assert isinstance(team, TeamDetail)
        assert team.team_id == 147
        assert team.abbreviation == "NYY"
        assert team.team_name == "Yankees"
        assert team.full_name == "New York Yankees"
        assert team.league_id == 103
        assert team.league_name == "American League"
        assert team.division_id == 201
        assert team.division_name == "American League East"
        assert team.venue_id == 3313
        assert team.active is True

    @patch("doubleday.util.mlb.urlopen")
    def test_missing_optional_fields(self, mock_urlopen):
        """Missing league/division/venue default to None or empty string."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "teams": [
                    {
                        "id": 999,
                        "abbreviation": "TST",
                        "teamName": "Test",
                        "name": "Test Team",
                    }
                ]
            }
        )

        result = fetch_teams_for_season(2025)

        team = result[0]
        assert team.league_id is None
        assert team.league_name == ""
        assert team.division_id is None
        assert team.division_name == ""
        assert team.venue_id is None
        assert team.active is False

    @patch("doubleday.util.mlb.urlopen")
    def test_empty_response(self, mock_urlopen):
        """Empty teams list returns empty list."""
        mock_urlopen.return_value = _mock_urlopen_response({"teams": []})

        result = fetch_teams_for_season(2025)

        assert result == []

    @patch("doubleday.util.mlb.urlopen")
    def test_uses_season_url(self, mock_urlopen):
        """Passes the season parameter in the URL."""
        mock_urlopen.return_value = _mock_urlopen_response({"teams": []})

        fetch_teams_for_season(2024)

        call_args = mock_urlopen.call_args[0][0]
        assert "season=2024" in call_args.full_url


class TestFetchVenues:
    """Tests for fetch_venues — fetches venue metadata per venue ID."""

    @patch("doubleday.util.mlb.urlopen")
    def test_parses_venue_with_location(self, mock_urlopen):
        """Parses all VenueInfo fields including coordinates."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "venues": [
                    {
                        "id": 3313,
                        "name": "Yankee Stadium",
                        "location": {
                            "address1": "1 East 161st Street",
                            "city": "Bronx",
                            "state": "New York",
                            "stateAbbrev": "NY",
                            "postalCode": "10451",
                            "defaultCoordinates": {
                                "latitude": 40.829,
                                "longitude": -73.926,
                            },
                            "elevation": 20.0,
                            "country": "USA",
                        },
                    }
                ]
            }
        )

        result = fetch_venues([3313])

        assert len(result) == 1
        venue = result[0]
        assert isinstance(venue, VenueInfo)
        assert venue.venue_id == 3313
        assert venue.name == "Yankee Stadium"
        assert venue.address1 == "1 East 161st Street"
        assert venue.city == "Bronx"
        assert venue.state == "New York"
        assert venue.state_abbrev == "NY"
        assert venue.postal_code == "10451"
        assert venue.latitude == 40.829
        assert venue.longitude == -73.926
        assert venue.elevation == 20.0
        assert venue.country == "USA"

    @patch("doubleday.util.mlb.urlopen")
    def test_missing_location_fields(self, mock_urlopen):
        """Venue with missing location defaults to empty strings and None."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "venues": [
                    {
                        "id": 9999,
                        "name": "Mystery Park",
                    }
                ]
            }
        )

        result = fetch_venues([9999])

        venue = result[0]
        assert venue.address1 == ""
        assert venue.city == ""
        assert venue.latitude is None
        assert venue.longitude is None
        assert venue.elevation is None

    @patch("doubleday.util.mlb.urlopen")
    def test_multiple_venues(self, mock_urlopen):
        """Fetches multiple venues with separate API calls."""

        def make_response(req):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "3313" in url:
                return _mock_urlopen_response({"venues": [{"id": 3313, "name": "Yankee Stadium"}]})
            return _mock_urlopen_response({"venues": [{"id": 15, "name": "Chase Field"}]})

        mock_urlopen.side_effect = make_response

        result = fetch_venues([3313, 15])

        assert len(result) == 2
        assert mock_urlopen.call_count == 2

    @patch("doubleday.util.mlb.urlopen")
    def test_skips_failed_venue(self, mock_urlopen):
        """Failed venue fetch is skipped, others still returned."""
        good_response = _mock_urlopen_response({"venues": [{"id": 3313, "name": "Yankee Stadium"}]})
        mock_urlopen.side_effect = [good_response, Exception("API error")]

        result = fetch_venues([3313, 9999])

        assert len(result) == 1
        assert result[0].venue_id == 3313

    def test_empty_input(self):
        """Empty venue ID list returns empty list without API calls."""
        result = fetch_venues([])

        assert result == []


class TestFetchSchedule:
    """Tests for fetch_schedule — fetches game schedule with umpire data."""

    @patch("doubleday.util.mlb.urlopen")
    def test_parses_game_with_hp_umpire(self, mock_urlopen):
        """Parses all GameInfo fields including home plate umpire."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 745678,
                                "gameType": "R",
                                "season": "2025",
                                "gameDate": "2025-06-15T18:05:00Z",
                                "officialDate": "2025-06-15",
                                "venue": {"id": 3313},
                                "dayNight": "night",
                                "teams": {
                                    "away": {
                                        "team": {"id": 121},
                                        "score": 3,
                                    },
                                    "home": {
                                        "team": {"id": 147},
                                        "score": 5,
                                    },
                                },
                                "officials": [
                                    {
                                        "official": {
                                            "id": 427542,
                                            "fullName": "Angel Hernandez",
                                        },
                                        "officialType": "Home Plate",
                                    },
                                    {
                                        "official": {
                                            "id": 111111,
                                            "fullName": "First Base Ump",
                                        },
                                        "officialType": "First Base",
                                    },
                                ],
                            }
                        ]
                    }
                ]
            }
        )

        result = fetch_schedule("2025-06-15")

        assert len(result) == 1
        game = result[0]
        assert isinstance(game, GameInfo)
        assert game.game_pk == 745678
        assert game.game_type == "R"
        assert game.season == 2025
        assert game.game_date == "2025-06-15T18:05:00Z"
        assert game.official_date == "2025-06-15"
        assert game.venue_id == 3313
        assert game.day_night == "night"
        assert game.away_team_id == 121
        assert game.home_team_id == 147
        assert game.away_score == 3
        assert game.home_score == 5
        assert game.hp_umpire_id == 427542
        assert game.hp_umpire_name == "Angel Hernandez"

    @patch("doubleday.util.mlb.urlopen")
    def test_no_hp_umpire(self, mock_urlopen):
        """Game without home plate umpire gets None/empty defaults."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 745679,
                                "gameType": "R",
                                "season": "2025",
                                "gameDate": "2025-06-15T18:05:00Z",
                                "officialDate": "2025-06-15",
                                "venue": {"id": 3313},
                                "dayNight": "day",
                                "teams": {
                                    "away": {"team": {"id": 121}},
                                    "home": {"team": {"id": 147}},
                                },
                                "officials": [],
                            }
                        ]
                    }
                ]
            }
        )

        result = fetch_schedule("2025-06-15")

        game = result[0]
        assert game.hp_umpire_id is None
        assert game.hp_umpire_name == ""
        assert game.away_score is None
        assert game.home_score is None

    @patch("doubleday.util.mlb.urlopen")
    def test_multiple_games_on_date(self, mock_urlopen):
        """Multiple games on the same date are all returned."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "dates": [
                    {
                        "games": [
                            {
                                "gamePk": 1,
                                "gameType": "R",
                                "season": "2025",
                                "gameDate": "2025-06-15T13:00:00Z",
                                "officialDate": "2025-06-15",
                                "venue": {"id": 1},
                                "dayNight": "day",
                                "teams": {
                                    "away": {"team": {"id": 100}},
                                    "home": {"team": {"id": 200}},
                                },
                            },
                            {
                                "gamePk": 2,
                                "gameType": "R",
                                "season": "2025",
                                "gameDate": "2025-06-15T19:00:00Z",
                                "officialDate": "2025-06-15",
                                "venue": {"id": 2},
                                "dayNight": "night",
                                "teams": {
                                    "away": {"team": {"id": 300}},
                                    "home": {"team": {"id": 400}},
                                },
                            },
                        ]
                    }
                ]
            }
        )

        result = fetch_schedule("2025-06-15")

        assert len(result) == 2
        assert result[0].game_pk == 1
        assert result[1].game_pk == 2

    @patch("doubleday.util.mlb.urlopen")
    def test_empty_schedule(self, mock_urlopen):
        """No games on date returns empty list."""
        mock_urlopen.return_value = _mock_urlopen_response({"dates": []})

        result = fetch_schedule("2025-12-25")

        assert result == []


class TestFetchUmpires:
    """Tests for fetch_umpires — batch-fetches umpire metadata from MLB API."""

    @patch("doubleday.util.mlb.urlopen")
    def test_single_umpire(self, mock_urlopen):
        """Fetches and parses a single umpire correctly."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "people": [
                    {
                        "id": 427542,
                        "fullName": "Angel Hernandez",
                    }
                ]
            }
        )

        result = fetch_umpires([427542])

        assert len(result) == 1
        umpire = result[427542]
        assert isinstance(umpire, UmpireInfo)
        assert umpire.umpire_id == 427542
        assert umpire.full_name == "Angel Hernandez"

    @patch("doubleday.util.mlb.urlopen")
    def test_batches_large_requests(self, mock_urlopen):
        """Requests with more than BATCH_SIZE IDs are split into batches."""
        total_ids = BATCH_SIZE + 10
        umpire_ids = list(range(1, total_ids + 1))

        def make_response(req):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            ids_param = url.split("personIds=")[1]
            ids = [int(x) for x in ids_param.split(",")]
            return _mock_urlopen_response({"people": [{"id": uid, "fullName": f"Umpire {uid}"} for uid in ids]})

        mock_urlopen.side_effect = make_response

        result = fetch_umpires(umpire_ids)

        assert len(result) == total_ids
        assert mock_urlopen.call_count == 2

    @patch("doubleday.util.mlb.urlopen")
    def test_partial_batch_failure(self, mock_urlopen):
        """If one batch fails, results from successful batches are returned."""
        total_ids = BATCH_SIZE + 10
        umpire_ids = list(range(1, total_ids + 1))

        first_batch_resp = _mock_urlopen_response(
            {"people": [{"id": uid, "fullName": f"Umpire {uid}"} for uid in range(1, BATCH_SIZE + 1)]}
        )
        mock_urlopen.side_effect = [first_batch_resp, Exception("API error")]

        result = fetch_umpires(umpire_ids)

        assert len(result) == BATCH_SIZE

    def test_empty_input(self):
        """Empty umpire ID list returns empty dict without API calls."""
        result = fetch_umpires([])

        assert result == {}

    @patch("doubleday.util.mlb.urlopen")
    def test_missing_full_name(self, mock_urlopen):
        """Umpire with missing fullName defaults to empty string."""
        mock_urlopen.return_value = _mock_urlopen_response(
            {
                "people": [
                    {
                        "id": 12345,
                    }
                ]
            }
        )

        result = fetch_umpires([12345])

        assert result[12345].full_name == ""
