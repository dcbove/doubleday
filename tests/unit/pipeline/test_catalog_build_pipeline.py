"""Unit tests for the catalog build pipeline (doubleday.pipeline.catalog_build.pipeline).

The catalog build extracts distinct player IDs from silver_pitches via Athena,
enriches them with metadata from the MLB Stats API (with cache fallback for
last-known-good semantics), and publishes catalog.json + manifest.json to S3.

These tests mock the Athena client, S3 client, and MLB API to verify: SQL
loading, player extraction, coverage extraction, enrichment cache read/write,
enrichment resolution with cache fallback, name normalization, catalog
construction, manifest construction, artifact publishing, and the end-to-end
orchestration flow.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from doubleday.pipeline.catalog_build.pipeline import (
    ENRICHMENT_CACHE_KEY,
    CatalogBuildResult,
    build_catalog,
    build_catalog_for_role,
    build_manifest,
    extract_coverage,
    extract_player_ids,
    load_enrichment_cache,
    load_sql,
    publish_artifacts,
    resolve_enrichment,
    save_enrichment_cache,
)


def _make_s3_mock():
    """Create a MagicMock S3 client with real ClientError on exceptions."""
    s3 = MagicMock()
    s3.exceptions.ClientError = ClientError
    return s3


class TestLoadSql:
    """Tests for load_sql — reads a SQL template file from a directory."""

    def test_reads_file_from_directory(self, tmp_path):
        """Reads the contents of a SQL file."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1")

        assert load_sql(tmp_path, "test.sql") == "SELECT 1"


class TestNormalizeName:
    """Tests for normalize_name — imported from mlb module and used for last_norm.

    Note: normalize_name is tested directly in test_mlb.py. These tests verify
    the import and usage within the pipeline context.
    """

    def test_import_works(self):
        """normalize_name is accessible from the pipeline module."""
        from doubleday.pipeline.catalog_build.pipeline import normalize_name

        assert normalize_name("Cole") == "cole"


class TestLoadEnrichmentCache:
    """Tests for load_enrichment_cache — reads the JSON cache from S3."""

    def test_happy_path(self):
        """Returns parsed cache dict from S3."""
        s3 = _make_s3_mock()
        cache_data = {"605151": {"first": "Gerrit", "last": "Cole"}}
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps(cache_data).encode()
        s3.get_object.return_value = {"Body": body_mock}

        result = load_enrichment_cache(s3, "lakehouse-bucket")

        assert result == cache_data
        s3.get_object.assert_called_once_with(
            Bucket="lakehouse-bucket",
            Key=ENRICHMENT_CACHE_KEY,
        )

    def test_no_such_key_returns_empty(self):
        """Returns empty dict when cache file does not exist."""
        s3 = _make_s3_mock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
            "GetObject",
        )

        result = load_enrichment_cache(s3, "lakehouse-bucket")

        assert result == {}

    def test_unexpected_error_re_raised(self):
        """Non-NoSuchKey errors are re-raised."""
        s3 = _make_s3_mock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "GetObject",
        )

        with pytest.raises(ClientError):
            load_enrichment_cache(s3, "lakehouse-bucket")


class TestSaveEnrichmentCache:
    """Tests for save_enrichment_cache — writes cache JSON to S3."""

    def test_correct_s3_key(self):
        """Writes to the expected S3 key."""
        s3 = MagicMock()
        cache = {"605151": {"first": "Gerrit", "last": "Cole"}}

        save_enrichment_cache(s3, "lakehouse-bucket", cache)

        s3.put_object.assert_called_once()
        call_kwargs = s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "lakehouse-bucket"
        assert call_kwargs["Key"] == ENRICHMENT_CACHE_KEY

    def test_int_keys_serialized_as_strings(self):
        """Cache with string keys is serialized correctly."""
        s3 = MagicMock()
        cache = {"12345": {"first": "Test", "last": "Player"}}

        save_enrichment_cache(s3, "bucket", cache)

        body = s3.put_object.call_args[1]["Body"]
        parsed = json.loads(body)
        assert "12345" in parsed


class TestResolveEnrichment:
    """Tests for resolve_enrichment — incremental fetch with cache reuse."""

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_all_fresh_from_api(self, mock_fetch):
        """New players not in cache are fetched from API."""
        mock_fetch.return_value = {
            605151: MagicMock(
                first_name="Gerrit",
                last_name="Cole",
                bats="R",
                throws="R",
                position="P",
                current_team_id=147,
            ),
        }

        merged, lkg, api_hit, cache_hit = resolve_enrichment([605151], {})

        assert 605151 in merged
        assert merged[605151]["first"] == "Gerrit"
        assert lkg is False
        assert api_hit == 1
        assert cache_hit == 0

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_cached_players_skip_api(self, mock_fetch):
        """Players already in cache are reused without an API call."""
        cache = {
            "605151": {
                "first": "Gerrit",
                "last": "Cole",
                "bats": "R",
                "throws": "R",
                "pos": "P",
                "current_team_id": 147,
            },
        }

        merged, lkg, api_hit, cache_hit = resolve_enrichment([605151], cache)

        assert 605151 in merged
        assert merged[605151]["first"] == "Gerrit"
        assert lkg is False
        assert api_hit == 0
        assert cache_hit == 1
        mock_fetch.assert_not_called()

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_incremental_mixed(self, mock_fetch):
        """Cached players reused, new players fetched from API."""
        mock_fetch.return_value = {
            999999: MagicMock(
                first_name="New",
                last_name="Player",
                bats="L",
                throws="L",
                position="OF",
                current_team_id=121,
            ),
        }
        cache = {
            "605151": {
                "first": "Gerrit",
                "last": "Cole",
                "bats": "R",
                "throws": "R",
                "pos": "P",
                "current_team_id": 147,
            },
        }

        merged, lkg, api_hit, cache_hit = resolve_enrichment([605151, 999999], cache)

        assert len(merged) == 2
        assert merged[605151]["first"] == "Gerrit"
        assert merged[999999]["first"] == "New"
        assert lkg is False
        assert api_hit == 1
        assert cache_hit == 1
        # Only the new player was fetched
        mock_fetch.assert_called_once_with([999999])

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_force_rebuild_fetches_all(self, mock_fetch):
        """Force rebuild fetches all players from API, ignoring cache."""
        mock_fetch.return_value = {
            605151: MagicMock(
                first_name="Gerrit",
                last_name="Cole",
                bats="R",
                throws="R",
                position="P",
                current_team_id=147,
            ),
        }
        cache = {
            "605151": {
                "first": "OldFirst",
                "last": "OldLast",
                "bats": "R",
                "throws": "R",
                "pos": "P",
                "current_team_id": 147,
            },
        }

        merged, lkg, api_hit, cache_hit = resolve_enrichment([605151], cache, force_rebuild=True)

        assert merged[605151]["first"] == "Gerrit"
        assert lkg is False
        assert api_hit == 1
        assert cache_hit == 0
        mock_fetch.assert_called_once_with([605151])

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_force_rebuild_cache_fallback(self, mock_fetch):
        """Force rebuild falls back to cache when API misses a player."""
        mock_fetch.return_value = {}
        cache = {
            "605151": {
                "first": "Gerrit",
                "last": "Cole",
                "bats": "R",
                "throws": "R",
                "pos": "P",
                "current_team_id": 147,
            },
        }

        merged, lkg, api_hit, cache_hit = resolve_enrichment([605151], cache, force_rebuild=True)

        assert 605151 in merged
        assert lkg is True
        assert api_hit == 0
        assert cache_hit == 1

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    def test_no_cache_no_api(self, mock_fetch):
        """Player with no cache and no API data is excluded."""
        mock_fetch.return_value = {}

        merged, lkg, api_hit, cache_hit = resolve_enrichment([999999], {})

        assert len(merged) == 0
        assert lkg is False
        assert api_hit == 0
        assert cache_hit == 0


class TestExtractPlayerIds:
    """Tests for extract_player_ids — runs extraction SQL via Athena."""

    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_correct_sql_loaded(self, mock_run, mock_results, tmp_path):
        """Loads the correct SQL file and formats season."""
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_extract_pitchers.sql").write_text(
            "SELECT pitcher FROM silver WHERE season = {season}"
        )  # noqa: E501
        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"player_id": "605151", "team_abbr": "NYY"}]

        result = extract_player_ids(
            MagicMock(),
            "db",
            "bucket",
            tmp_path,
            2024,
            "pitchers",
        )

        assert result == [{"player_id": "605151", "team_abbr": "NYY"}]
        sql_arg = mock_run.call_args.args[1]
        assert "season = 2024" in sql_arg

    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_batters_role(self, mock_run, mock_results, tmp_path):
        """Loads the batters SQL file for role='batters'."""
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_extract_batters.sql").write_text(
            "SELECT batter FROM silver WHERE season = {season}"
        )  # noqa: E501
        mock_run.return_value = "exec-1"
        mock_results.return_value = [{"player_id": "123", "team_abbr": "BOS"}]

        result = extract_player_ids(
            MagicMock(),
            "db",
            "bucket",
            tmp_path,
            2025,
            "batters",
        )

        assert result == [{"player_id": "123", "team_abbr": "BOS"}]


class TestExtractCoverage:
    """Tests for extract_coverage — runs coverage SQL via Athena."""

    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_returns_coverage_dict(self, mock_run, mock_results, tmp_path):
        """Returns first and last game dates."""
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_coverage.sql").write_text(
            "SELECT MIN(game_date) FROM silver WHERE season = {season}"
        )  # noqa: E501
        mock_run.return_value = "exec-1"
        mock_results.return_value = [
            {"first_game_date": "2024-03-28", "last_game_date": "2024-09-29"},
        ]

        result = extract_coverage(MagicMock(), "db", "bucket", tmp_path, 2024)

        assert result["first_game_date"] == "2024-03-28"
        assert result["last_game_date"] == "2024-09-29"

    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_empty_result_returns_defaults(self, mock_run, mock_results, tmp_path):
        """Empty results return empty string defaults."""
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_coverage.sql").write_text("SELECT 1 WHERE season = {season}")
        mock_run.return_value = "exec-1"
        mock_results.return_value = []

        result = extract_coverage(MagicMock(), "db", "bucket", tmp_path, 2024)

        assert result == {"first_game_date": "", "last_game_date": ""}


class TestBuildCatalog:
    """Tests for build_catalog — assembles the catalog artifact dict."""

    def test_schema_version(self):
        """Catalog has schema_version 1."""
        catalog = build_catalog(2024, "pitchers", [], {})

        assert catalog["schema_version"] == 1

    def test_player_sorting(self):
        """Players are sorted by last name, then first name."""
        players = [
            {"last": "Zack", "first": "Bob", "id": 2},
            {"last": "Adams", "first": "Charlie", "id": 3},
            {"last": "Adams", "first": "Alice", "id": 1},
        ]

        catalog = build_catalog(2024, "pitchers", players, {})

        assert [p["id"] for p in catalog["players"]] == [1, 3, 2]

    def test_string_team_keys(self):
        """Teams dict uses string keys."""
        teams = {"147": {"abbr": "NYY", "name": "Yankees"}}

        catalog = build_catalog(2024, "pitchers", [], teams)

        assert "147" in catalog["teams"]

    def test_season_and_role(self):
        """Catalog includes season and role."""
        catalog = build_catalog(2025, "batters", [], {})

        assert catalog["season"] == 2025
        assert catalog["role"] == "batters"


class TestBuildManifest:
    """Tests for build_manifest — assembles the manifest artifact dict."""

    def test_all_fields_present(self):
        """Manifest includes all required fields."""
        coverage = {"first_game_date": "2024-03-28", "last_game_date": "2024-09-29"}

        manifest = build_manifest(2024, "pitchers", coverage, 50000, 500, 30, False)

        assert manifest["schema_version"] == 1
        assert manifest["season"] == 2024
        assert manifest["role"] == "pitchers"
        assert "generated_at" in manifest
        assert manifest["coverage"]["first_game_date_seen"] == "2024-03-28"
        assert manifest["coverage"]["last_game_date_seen"] == "2024-09-29"
        assert manifest["counts"]["players"] == 500
        assert manifest["counts"]["teams"] == 30
        assert manifest["catalog"]["bytes"] == 50000
        assert manifest["enrichment"]["last_known_good"] is False

    def test_etag_format(self):
        """Etag is a quoted hex string."""
        manifest = build_manifest(2024, "pitchers", {}, 100, 10, 5, True)

        etag = manifest["catalog"]["etag"]
        assert etag.startswith('"')
        assert etag.endswith('"')
        # Inner value should be hex
        inner = etag.strip('"')
        int(inner, 16)  # Should not raise

    def test_byte_count(self):
        """Catalog byte count is included."""
        manifest = build_manifest(2024, "pitchers", {}, 812345, 100, 30, False)

        assert manifest["catalog"]["bytes"] == 812345

    def test_catalog_url_format(self):
        """Catalog URL follows the expected pattern."""
        manifest = build_manifest(2024, "pitchers", {}, 100, 10, 5, False)

        assert manifest["catalog"]["url"] == "/static/catalogs/pitchers/season=2024/catalog.json"


class TestPublishArtifacts:
    """Tests for publish_artifacts — writes catalog and manifest to S3."""

    def test_publishes_both_files(self):
        """Calls put_object for both catalog.json and manifest.json."""
        s3 = MagicMock()
        manifest = {"schema_version": 1}
        catalog_body = b'{"players":[]}'

        publish_artifacts(s3, "frontend-bucket", 2024, "pitchers", catalog_body, manifest)

        assert s3.put_object.call_count == 2
        calls = s3.put_object.call_args_list

        # First call: catalog
        assert calls[0][1]["Key"] == "static/catalogs/pitchers/season=2024/catalog.json"
        assert calls[0][1]["Body"] == catalog_body
        assert calls[0][1]["ContentType"] == "application/json"

        # Second call: manifest
        assert calls[1][1]["Key"] == "static/catalogs/pitchers/season=2024/manifest.json"
        assert calls[1][1]["ContentType"] == "application/json"

    def test_correct_bucket(self):
        """Publishes to the specified frontend bucket."""
        s3 = MagicMock()

        publish_artifacts(s3, "my-frontend", 2025, "batters", b"{}", {"v": 1})

        for call in s3.put_object.call_args_list:
            assert call[1]["Bucket"] == "my-frontend"


class TestBuildCatalogForRole:
    """Tests for build_catalog_for_role — end-to-end orchestration."""

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_teams")
    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_end_to_end(self, mock_run, mock_results, mock_fetch_players, mock_fetch_teams, tmp_path):
        """Full orchestration produces correct result and publishes artifacts."""
        # Setup SQL files
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_extract_pitchers.sql").write_text(
            "SELECT pitcher FROM silver WHERE season = {season}"
        )  # noqa: E501
        (tmp_path / "pipeline" / "catalog_coverage.sql").write_text(
            "SELECT coverage FROM silver WHERE season = {season}"
        )  # noqa: E501

        # Mock Athena
        mock_run.side_effect = ["exec-extract", "exec-coverage"]
        mock_results.side_effect = [
            # extract_player_ids result
            [{"player_id": "605151", "team_abbr": "NYY"}],
            # extract_coverage result
            [{"first_game_date": "2024-03-28", "last_game_date": "2024-09-29"}],
        ]

        # Mock MLB API
        mock_fetch_teams.return_value = {
            "NYY": MagicMock(team_id=147, abbreviation="NYY", team_name="Yankees"),
        }
        mock_fetch_players.return_value = {
            605151: MagicMock(
                first_name="Gerrit",
                last_name="Cole",
                bats="R",
                throws="R",
                position="P",
                current_team_id=147,
            ),
        }

        # Mock S3
        s3 = _make_s3_mock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
            "GetObject",
        )

        result = build_catalog_for_role(
            MagicMock(),
            s3,
            "db",
            "output-bucket",
            "lakehouse-bucket",
            "frontend-bucket",
            tmp_path,
            2024,
            "pitchers",
        )

        assert isinstance(result, CatalogBuildResult)
        assert result.season == 2024
        assert result.role == "pitchers"
        assert result.player_count == 1
        assert result.team_count >= 1
        assert result.catalog_bytes > 0
        assert result.last_known_good is False

        # Verify S3 put_object called for cache + catalog + manifest
        put_calls = s3.put_object.call_args_list
        put_keys = [call[1]["Key"] for call in put_calls]
        assert ENRICHMENT_CACHE_KEY in put_keys
        assert "static/catalogs/pitchers/season=2024/catalog.json" in put_keys
        assert "static/catalogs/pitchers/season=2024/manifest.json" in put_keys

    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_teams")
    @patch("doubleday.pipeline.catalog_build.pipeline.fetch_players")
    @patch("doubleday.pipeline.catalog_build.pipeline.get_query_results")
    @patch("doubleday.pipeline.catalog_build.pipeline.run_query")
    def test_excludes_unenriched_players(self, mock_run, mock_results, mock_fetch_players, mock_fetch_teams, tmp_path):
        """Players with no enrichment data are excluded from the catalog."""
        (tmp_path / "pipeline").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "catalog_extract_pitchers.sql").write_text("SELECT 1 WHERE season = {season}")
        (tmp_path / "pipeline" / "catalog_coverage.sql").write_text("SELECT 1 WHERE season = {season}")

        mock_run.side_effect = ["exec-1", "exec-2"]
        mock_results.side_effect = [
            [{"player_id": "111", "team_abbr": "NYY"}, {"player_id": "222", "team_abbr": "BOS"}],
            [{"first_game_date": "2024-03-28", "last_game_date": "2024-09-29"}],
        ]

        # Only player 111 has enrichment
        mock_fetch_teams.return_value = {
            "NYY": MagicMock(team_id=147, abbreviation="NYY", team_name="Yankees"),
        }
        mock_fetch_players.return_value = {
            111: MagicMock(
                first_name="Test",
                last_name="Player",
                bats="R",
                throws="R",
                position="P",
                current_team_id=147,
            ),
        }

        s3 = _make_s3_mock()
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
            "GetObject",
        )

        result = build_catalog_for_role(
            MagicMock(),
            s3,
            "db",
            "bucket",
            "lakehouse",
            "frontend",
            tmp_path,
            2024,
            "pitchers",
        )

        assert result.player_count == 1
        assert result.enrichment_missing == 1
