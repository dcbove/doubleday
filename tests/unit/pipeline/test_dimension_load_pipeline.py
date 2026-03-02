"""Unit tests for the dimension load pipeline.

Tests the two-phase load (bronze cache + silver INSERT) for each dimension:
teams, venues, games, umpires, players. Mocks MLB API, S3, and Athena.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from doubleday.pipeline.dimension_load.pipeline import (
    DimensionLoadResult,
    _bronze_key,
    _delete_partition,
    _enrichment_to_row,
    _insert_rows,
    _retain_current_team_ids,
    load_dimension,
)
from doubleday.util.mlb import PlayerEnrichment

# ---------------------------------------------------------------------------
# Bronze key tests
# ---------------------------------------------------------------------------


class TestBronzeKey:
    """Tests for _bronze_key — S3 key generation for bronze cache files."""

    def test_per_season_key(self):
        """Per-season dimensions use season-partitioned path."""
        assert _bronze_key("teams", 2025) == "bronze_dimensions/teams/season=2025/data.json"

    def test_per_date_key(self):
        """Games dimension uses date-partitioned path."""
        key = _bronze_key("games", 2025, "2025-06-15")
        assert key == "bronze_dimensions/games/season=2025/game_date=2025-06-15/data.json"

    def test_players_key(self):
        """Players dimension uses season-partitioned path."""
        assert _bronze_key("players", 2024) == "bronze_dimensions/players/season=2024/data.json"


# ---------------------------------------------------------------------------
# Delete partition tests
# ---------------------------------------------------------------------------


class TestDeletePartition:
    """Tests for _delete_partition — SQL DELETE via Athena."""

    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_generates_correct_sql(self, mock_run):
        """Generates DELETE FROM table WHERE clause."""
        mock_run.return_value = "exec-1"
        client = MagicMock()

        result = _delete_partition(client, "db", "bucket", "silver_teams", "season = 2025")

        assert result == "exec-1"
        sql = mock_run.call_args[0][1]
        assert sql == "DELETE FROM silver_teams WHERE season = 2025"


# ---------------------------------------------------------------------------
# Insert rows tests
# ---------------------------------------------------------------------------


class TestInsertRows:
    """Tests for _insert_rows — batched VALUES INSERT via Athena."""

    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_single_batch(self, mock_run):
        """Small row count produces one INSERT statement."""
        mock_run.return_value = "exec-1"
        client = MagicMock()
        rows = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

        total = _insert_rows(client, "db", "bucket", "t", ["id", "name"], rows)

        assert total == 2
        assert mock_run.call_count == 1
        sql = mock_run.call_args[0][1]
        assert "INSERT INTO t" in sql
        assert "(1, 'A')" in sql
        assert "(2, 'B')" in sql

    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_multiple_batches(self, mock_run):
        """Large row count splits into multiple INSERT statements."""
        mock_run.return_value = "exec-1"
        client = MagicMock()
        rows = [{"id": i} for i in range(250)]

        total = _insert_rows(client, "db", "bucket", "t", ["id"], rows)

        assert total == 250
        assert mock_run.call_count == 3  # 100 + 100 + 50


# ---------------------------------------------------------------------------
# Enrichment to row tests
# ---------------------------------------------------------------------------


class TestEnrichmentToRow:
    """Tests for _enrichment_to_row — PlayerEnrichment to bronze dict."""

    def test_basic_conversion(self):
        """Converts a PlayerEnrichment to a dict matching silver_players columns."""
        enrichment = PlayerEnrichment(
            player_id=660271,
            first_name="Shohei",
            last_name="Ohtani",
            bats="L",
            throws="R",
            position="DH",
            current_team_id=119,
            headshot_url="https://example.com/660271.png",
        )

        row = _enrichment_to_row(enrichment, 2025)

        assert row["player_id"] == 660271
        assert row["first_name"] == "Shohei"
        assert row["last_name"] == "Ohtani"
        assert row["last_norm"] == "ohtani"
        assert row["bats"] == "L"
        assert row["throws"] == "R"
        assert row["position"] == "DH"
        assert row["current_team_id"] == 119
        assert row["season"] == 2025

    def test_none_current_team(self):
        """Players without a current team have None for current_team_id."""
        enrichment = PlayerEnrichment(
            player_id=123,
            first_name="Test",
            last_name="Player",
            bats="R",
            throws="R",
            position="P",
            current_team_id=None,
            headshot_url="https://example.com/123.png",
        )

        row = _enrichment_to_row(enrichment, 2025)
        assert row["current_team_id"] is None

    def test_accented_name_normalization(self):
        """Accented names are normalized for last_norm."""
        enrichment = PlayerEnrichment(
            player_id=456,
            first_name="José",
            last_name="Ramírez",
            bats="S",
            throws="R",
            position="3B",
            current_team_id=114,
            headshot_url="https://example.com/456.png",
        )

        row = _enrichment_to_row(enrichment, 2025)
        assert row["last_norm"] == "ramirez"
        assert row["last_name"] == "Ramírez"


# ---------------------------------------------------------------------------
# Retain current_team_id tests
# ---------------------------------------------------------------------------


class TestRetainCurrentTeamIds:
    """Tests for _retain_current_team_ids — non-regression of team affiliations."""

    def test_retains_previous_team_when_api_returns_none(self):
        """Players with None current_team_id get previous value from cache."""
        cache = {
            "660271": {"player_id": 660271, "current_team_id": 119, "season": 2025},
        }
        fresh = {
            "660271": {"player_id": 660271, "current_team_id": None, "season": 2025},
        }

        _retain_current_team_ids(cache, fresh)

        assert fresh["660271"]["current_team_id"] == 119

    def test_does_not_override_api_team(self):
        """Players with a valid current_team_id from API keep the new value."""
        cache = {
            "660271": {"player_id": 660271, "current_team_id": 119, "season": 2025},
        }
        fresh = {
            "660271": {"player_id": 660271, "current_team_id": 137, "season": 2025},
        }

        _retain_current_team_ids(cache, fresh)

        assert fresh["660271"]["current_team_id"] == 137

    def test_handles_empty_cache(self):
        """First load with no cache does not set current_team_id."""
        cache: dict[str, dict] = {}
        fresh = {
            "660271": {"player_id": 660271, "current_team_id": None, "season": 2025},
        }

        _retain_current_team_ids(cache, fresh)

        assert fresh["660271"]["current_team_id"] is None

    def test_new_player_not_in_cache(self):
        """New player not in cache keeps its API value."""
        cache = {
            "660271": {"player_id": 660271, "current_team_id": 119, "season": 2025},
        }
        fresh = {
            "592450": {"player_id": 592450, "current_team_id": None, "season": 2025},
        }

        _retain_current_team_ids(cache, fresh)

        assert fresh["592450"]["current_team_id"] is None


# ---------------------------------------------------------------------------
# Load dimension dispatcher tests
# ---------------------------------------------------------------------------


class TestLoadDimension:
    """Tests for load_dimension — the top-level dispatcher."""

    def test_invalid_dimension_raises(self):
        """Unknown dimension name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown dimension"):
            load_dimension(MagicMock(), MagicMock(), "bucket", "db", "out", "invalid", 2025)

    @patch("doubleday.pipeline.dimension_load.pipeline._load_teams")
    def test_dispatches_to_teams(self, mock_load):
        """Dimension 'teams' dispatches to _load_teams."""
        mock_load.return_value = DimensionLoadResult(records_loaded=30, bronze_cached=False)
        s3 = MagicMock()
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "teams", 2025)

        mock_load.assert_called_once_with(s3, athena, "bucket", "db", "out", 2025, False)
        assert result.records_loaded == 30

    @patch("doubleday.pipeline.dimension_load.pipeline._load_games")
    def test_dispatches_to_games_with_dates(self, mock_load):
        """Dimension 'games' passes game_dates to _load_games."""
        mock_load.return_value = DimensionLoadResult(records_loaded=15, bronze_cached=True)
        s3 = MagicMock()
        athena = MagicMock()

        result = load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "games",
            2025,
            game_dates=["2025-06-15"],
        )

        mock_load.assert_called_once_with(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            2025,
            ["2025-06-15"],
            False,
        )
        assert result.records_loaded == 15

    @patch("doubleday.pipeline.dimension_load.pipeline._load_umpires")
    def test_dispatches_to_umpires_with_dates(self, mock_load):
        """Dimension 'umpires' passes game_dates for date-scoped queries."""
        mock_load.return_value = DimensionLoadResult(records_loaded=5, bronze_cached=False)
        s3 = MagicMock()
        athena = MagicMock()

        result = load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "umpires",
            2025,
            game_dates=["2025-06-15"],
        )

        mock_load.assert_called_once_with(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            2025,
            ["2025-06-15"],
            False,
        )
        assert result.records_loaded == 5

    @patch("doubleday.pipeline.dimension_load.pipeline._load_players")
    def test_dispatches_to_players_with_dates(self, mock_load):
        """Dimension 'players' passes game_dates for date-scoped queries."""
        mock_load.return_value = DimensionLoadResult(records_loaded=50, bronze_cached=False)
        s3 = MagicMock()
        athena = MagicMock()

        result = load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "players",
            2025,
            game_dates=["2025-06-15"],
        )

        mock_load.assert_called_once_with(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            2025,
            ["2025-06-15"],
            False,
        )
        assert result.records_loaded == 50


# ---------------------------------------------------------------------------
# Teams loader tests
# ---------------------------------------------------------------------------


class TestLoadTeams:
    """Tests for the teams dimension loader (bronze + silver)."""

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_teams_for_season")
    def test_fresh_fetch_writes_bronze_and_silver(self, mock_fetch, mock_delete, mock_insert):
        """First load fetches from API, writes bronze, loads silver."""
        from doubleday.util.mlb import TeamDetail

        mock_fetch.return_value = [
            TeamDetail(
                team_id=147,
                abbreviation="NYY",
                team_name="Yankees",
                full_name="New York Yankees",
                league_id=103,
                league_name="American League",
                division_id=201,
                division_name="American League East",
                venue_id=3313,
                active=True,
            ),
        ]
        mock_insert.return_value = 1

        s3 = MagicMock()
        # Bronze does not exist
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "teams", 2025)

        assert result.records_loaded == 1
        assert result.bronze_cached is False
        # Verify bronze was written
        s3.put_object.assert_called_once()
        put_call = s3.put_object.call_args
        assert put_call.kwargs["Key"] == "bronze_dimensions/teams/season=2025/data.json"
        bronze_data = json.loads(put_call.kwargs["Body"].decode("utf-8"))
        assert len(bronze_data) == 1
        assert bronze_data[0]["team_id"] == 147
        assert bronze_data[0]["active"] is True

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    def test_cache_hit_reads_bronze(self, mock_delete, mock_insert):
        """When bronze exists, reads from S3 without calling MLB API."""
        mock_insert.return_value = 1

        s3 = MagicMock()
        # Bronze exists
        s3.head_object.return_value = {}
        bronze_body = json.dumps([{"team_id": 147, "abbreviation": "NYY", "season": 2025}])
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=bronze_body.encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "teams", 2025)

        assert result.bronze_cached is True
        # API should not have been called (no fetch_teams_for_season mock needed)


# ---------------------------------------------------------------------------
# Venues loader tests
# ---------------------------------------------------------------------------


class TestLoadVenues:
    """Tests for the venues dimension loader (reads teams bronze for venue_ids)."""

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_venues")
    def test_reads_teams_bronze_for_venue_ids(self, mock_fetch, mock_delete, mock_insert):
        """Venues loader reads teams bronze to get venue_ids."""
        from doubleday.util.mlb import VenueInfo

        mock_fetch.return_value = [
            VenueInfo(
                venue_id=3313,
                name="Yankee Stadium",
                address1="1 E 161st St",
                city="Bronx",
                state="New York",
                state_abbrev="NY",
                postal_code="10451",
                latitude=40.829,
                longitude=-73.926,
                elevation=0.0,
                country="USA",
            ),
        ]
        mock_insert.return_value = 1

        s3 = MagicMock()
        # Venues bronze does NOT exist (404)
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )

        def head_side_effect(Bucket, Key):  # noqa: N803
            if "venues" in Key:
                raise s3.exceptions.ClientError(error_response, "HeadObject")
            return {}  # teams bronze exists

        s3.head_object.side_effect = head_side_effect

        # Teams bronze cache
        teams_bronze = json.dumps(
            [
                {"team_id": 147, "venue_id": 3313, "season": 2025},
                {"team_id": 111, "venue_id": 3313, "season": 2025},  # same venue, deduped
            ]
        )
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=teams_bronze.encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "venues", 2025)

        assert result.records_loaded == 1
        # Verify fetch_venues was called with deduplicated venue_ids
        mock_fetch.assert_called_once_with([3313])


# ---------------------------------------------------------------------------
# Games loader tests
# ---------------------------------------------------------------------------


class TestLoadGames:
    """Tests for the games dimension loader (per-date bronze caching)."""

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_schedule")
    def test_loads_multiple_dates(self, mock_fetch, mock_delete, mock_insert):
        """Games loader fetches per date and combines for silver INSERT."""
        from doubleday.util.mlb import GameInfo

        mock_fetch.side_effect = [
            [
                GameInfo(
                    game_pk=1,
                    game_type="R",
                    season=2025,
                    game_date="2025-06-15T00:00:00Z",
                    official_date="2025-06-15",
                    venue_id=3313,
                    day_night="night",
                    away_team_id=111,
                    home_team_id=147,
                    away_score=3,
                    home_score=5,
                    hp_umpire_id=427542,
                    hp_umpire_name="Pat Hoberg",
                )
            ],
            [
                GameInfo(
                    game_pk=2,
                    game_type="R",
                    season=2025,
                    game_date="2025-06-16T00:00:00Z",
                    official_date="2025-06-16",
                    venue_id=3313,
                    day_night="day",
                    away_team_id=111,
                    home_team_id=147,
                    away_score=1,
                    home_score=2,
                    hp_umpire_id=427543,
                    hp_umpire_name="Angel Hernandez",
                )
            ],
        ]
        mock_insert.return_value = 2

        s3 = MagicMock()
        # No bronze cache
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        result = load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "games",
            2025,
            game_dates=["2025-06-15", "2025-06-16"],
        )

        assert result.records_loaded == 2
        assert result.bronze_cached is False
        # Two bronze files written (one per date)
        assert s3.put_object.call_count == 2

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    def test_delete_uses_official_date_in_clause(self, mock_delete, mock_insert):
        """Games DELETE uses official_date IN (...) clause."""
        mock_delete.return_value = "exec-1"
        mock_insert.return_value = 0

        s3 = MagicMock()
        # All dates cached
        s3.head_object.return_value = {}
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b'[{"game_pk": 1, "season": 2025}]')),
        }
        athena = MagicMock()

        load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "games",
            2025,
            game_dates=["2025-06-15", "2025-06-16"],
        )

        delete_call = mock_delete.call_args
        where = delete_call[0][4]  # where_clause positional arg
        assert "official_date IN" in where
        assert "'2025-06-15'" in where
        assert "'2025-06-16'" in where


# ---------------------------------------------------------------------------
# Umpires loader tests
# ---------------------------------------------------------------------------


class TestLoadUmpires:
    """Tests for the umpires dimension loader (additive bronze)."""

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_umpires")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_first_run_fetches_all_and_writes_cache(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """First run with no bronze cache fetches all IDs from API."""
        from doubleday.util.mlb import UmpireInfo

        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {"hp_umpire_id": "427542"},
            {"hp_umpire_id": "427543"},
        ]
        mock_fetch.return_value = {
            427542: UmpireInfo(umpire_id=427542, full_name="Pat Hoberg"),
            427543: UmpireInfo(umpire_id=427543, full_name="Angel Hernandez"),
        }
        mock_insert.return_value = 2

        s3 = MagicMock()
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "umpires", 2025)

        assert result.records_loaded == 2
        assert result.bronze_cached is False
        # Verify silver_games query
        first_sql = mock_run.call_args_list[0][0][1]
        assert "silver_games" in first_sql
        assert "DISTINCT hp_umpire_id" in first_sql
        mock_fetch.assert_called_once_with([427542, 427543])
        # Verify bronze cache written as dict keyed by ID
        s3.put_object.assert_called_once()
        bronze_data = json.loads(s3.put_object.call_args.kwargs["Body"].decode("utf-8"))
        assert "427542" in bronze_data
        assert "427543" in bronze_data

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_umpires")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_second_run_only_fetches_new_ids(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """Second run with existing cache only fetches newly discovered IDs."""
        from doubleday.util.mlb import UmpireInfo

        mock_run.return_value = "exec-1"
        # silver_pitches now has 3 umpires (one new)
        mock_results.return_value = [
            {"hp_umpire_id": "427542"},
            {"hp_umpire_id": "427543"},
            {"hp_umpire_id": "427544"},
        ]
        # API only called for the new one
        mock_fetch.return_value = {
            427544: UmpireInfo(umpire_id=427544, full_name="New Umpire"),
        }
        mock_insert.return_value = 3

        s3 = MagicMock()
        # Bronze cache exists with 2 umpires
        s3.head_object.return_value = {}
        existing_cache = {
            "427542": {"umpire_id": 427542, "full_name": "Pat Hoberg", "season": 2025},
            "427543": {"umpire_id": 427543, "full_name": "Angel Hernandez", "season": 2025},
        }
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(existing_cache).encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "umpires", 2025)

        assert result.records_loaded == 3
        assert result.bronze_cached is False
        # Only the new ID should be fetched
        mock_fetch.assert_called_once_with([427544])

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_no_new_ids_skips_api_call(
        self,
        mock_run,
        mock_results,
        mock_delete,
        mock_insert,
    ):
        """When all IDs are in cache, MLB API is not called."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"hp_umpire_id": "427542"}]
        mock_insert.return_value = 1

        s3 = MagicMock()
        s3.head_object.return_value = {}
        existing_cache = {
            "427542": {"umpire_id": 427542, "full_name": "Pat Hoberg", "season": 2025},
        }
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(existing_cache).encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "umpires", 2025)

        assert result.records_loaded == 1
        assert result.bronze_cached is True
        # No put_object call (cache unchanged)
        s3.put_object.assert_not_called()

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_umpires")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_date_scoped_query(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """When game_dates is provided, silver_games query is date-scoped."""
        from doubleday.util.mlb import UmpireInfo

        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"hp_umpire_id": "427542"}]
        mock_fetch.return_value = {
            427542: UmpireInfo(umpire_id=427542, full_name="Pat Hoberg"),
        }
        mock_insert.return_value = 1

        s3 = MagicMock()
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "umpires",
            2025,
            game_dates=["2025-06-15"],
        )

        first_sql = mock_run.call_args_list[0][0][1]
        assert "official_date IN ('2025-06-15')" in first_sql


# ---------------------------------------------------------------------------
# Players loader tests
# ---------------------------------------------------------------------------


class TestLoadPlayers:
    """Tests for the players dimension loader (additive bronze)."""

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_players")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_first_run_fetches_all(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """First run unions pitchers/batters and fetches all from API."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {"player_id": "592450"},
            {"player_id": "660271"},
        ]
        mock_fetch.return_value = {
            660271: PlayerEnrichment(
                player_id=660271,
                first_name="Shohei",
                last_name="Ohtani",
                bats="L",
                throws="R",
                position="DH",
                current_team_id=119,
                headshot_url="https://example.com/660271.png",
            ),
            592450: PlayerEnrichment(
                player_id=592450,
                first_name="Aaron",
                last_name="Judge",
                bats="R",
                throws="R",
                position="RF",
                current_team_id=147,
                headshot_url="https://example.com/592450.png",
            ),
        }
        mock_insert.return_value = 2

        s3 = MagicMock()
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "players", 2025)

        assert result.records_loaded == 2
        assert result.bronze_cached is False
        # Verify the UNION query against silver_pitches
        first_sql = mock_run.call_args_list[0][0][1]
        assert "pitcher" in first_sql
        assert "batter" in first_sql
        assert "UNION" in first_sql
        # Verify bronze cache written as dict
        bronze_data = json.loads(s3.put_object.call_args.kwargs["Body"].decode("utf-8"))
        assert "660271" in bronze_data
        assert "592450" in bronze_data

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_players")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_retains_current_team_id_on_merge(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """When API returns None for current_team_id, cache value is retained."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {"player_id": "660271"},
            {"player_id": "592450"},
        ]
        # Only new player fetched; API returns None for current_team_id
        mock_fetch.return_value = {
            592450: PlayerEnrichment(
                player_id=592450,
                first_name="Aaron",
                last_name="Judge",
                bats="R",
                throws="R",
                position="RF",
                current_team_id=None,
                headshot_url="https://example.com/592450.png",
            ),
        }
        mock_insert.return_value = 2

        s3 = MagicMock()
        s3.head_object.return_value = {}
        # Existing cache has Ohtani with team 119
        existing_cache = {
            "660271": {
                "player_id": 660271,
                "first_name": "Shohei",
                "last_name": "Ohtani",
                "last_norm": "ohtani",
                "bats": "L",
                "throws": "R",
                "position": "DH",
                "current_team_id": 119,
                "headshot_url": "https://example.com/660271.png",
                "season": 2025,
            },
        }
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(existing_cache).encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "players", 2025)

        assert result.records_loaded == 2
        # Verify the merged cache has Judge with None (no prior to retain)
        bronze_data = json.loads(s3.put_object.call_args.kwargs["Body"].decode("utf-8"))
        assert bronze_data["592450"]["current_team_id"] is None
        # Ohtani is still in cache from before
        assert bronze_data["660271"]["current_team_id"] == 119

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_no_new_ids_skips_api_call(
        self,
        mock_run,
        mock_results,
        mock_delete,
        mock_insert,
    ):
        """When all player IDs are in cache, MLB API is not called."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"player_id": "660271"}]
        mock_insert.return_value = 1

        s3 = MagicMock()
        s3.head_object.return_value = {}
        existing_cache = {
            "660271": {
                "player_id": 660271,
                "first_name": "Shohei",
                "last_name": "Ohtani",
                "last_norm": "ohtani",
                "bats": "L",
                "throws": "R",
                "position": "DH",
                "current_team_id": 119,
                "headshot_url": "https://example.com/660271.png",
                "season": 2025,
            },
        }
        s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(existing_cache).encode("utf-8"))),
        }
        athena = MagicMock()

        result = load_dimension(s3, athena, "bucket", "db", "out", "players", 2025)

        assert result.records_loaded == 1
        assert result.bronze_cached is True
        s3.put_object.assert_not_called()

    @patch("doubleday.pipeline.dimension_load.pipeline._insert_rows")
    @patch("doubleday.pipeline.dimension_load.pipeline._delete_partition")
    @patch("doubleday.pipeline.dimension_load.pipeline.fetch_players")
    @patch("doubleday.pipeline.dimension_load.pipeline.get_query_results")
    @patch("doubleday.pipeline.dimension_load.pipeline.run_query")
    def test_date_scoped_query(
        self,
        mock_run,
        mock_results,
        mock_fetch,
        mock_delete,
        mock_insert,
    ):
        """When game_dates is provided, silver_pitches query is date-scoped."""
        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"player_id": "660271"}]
        mock_fetch.return_value = {
            660271: PlayerEnrichment(
                player_id=660271,
                first_name="Shohei",
                last_name="Ohtani",
                bats="L",
                throws="R",
                position="DH",
                current_team_id=119,
                headshot_url="https://example.com/660271.png",
            ),
        }
        mock_insert.return_value = 1

        s3 = MagicMock()
        error_response = {"Error": {"Code": "404"}}
        s3.exceptions.ClientError = type(
            "ClientError",
            (Exception,),
            {
                "__init__": lambda self, resp, op: (
                    super(type(self), self).__init__(f"{op}: {resp}"),
                    setattr(self, "response", resp),
                )[-1],
            },
        )
        s3.head_object.side_effect = s3.exceptions.ClientError(error_response, "HeadObject")
        athena = MagicMock()

        load_dimension(
            s3,
            athena,
            "bucket",
            "db",
            "out",
            "players",
            2025,
            game_dates=["2025-06-15"],
        )

        first_sql = mock_run.call_args_list[0][0][1]
        assert "game_date IN (DATE '2025-06-15')" in first_sql
