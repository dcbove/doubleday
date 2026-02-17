"""Integration tests for the catalog build pipeline.

Calls the catalog build pipeline function directly against real AWS resources
(Athena, S3, MLB Stats API). Unlike the Lambda invocation tests in test_lambdas.py,
these tests exercise the pipeline function without a deployed Lambda, using real
boto3 clients pointed at the dev environment.

Requires:
- Valid AWS credentials with Athena query and S3 read/write permissions
- Silver data already loaded for season 2024 (run the pipeline first)
- Network access to the MLB Stats API (statsapi.mlb.com)

Run with: make test-integration
"""

import json
from pathlib import Path

import boto3
import pytest

from doubleday.pipeline.catalog_build.pipeline import (
    CatalogBuildResult,
    build_catalog_for_role,
    extract_coverage,
    extract_player_ids,
    load_enrichment_cache,
)
from doubleday.util.athena import run_query

athena_client = boto3.client("athena")
s3_client = boto3.client("s3")

DATABASE = "doubleday_dev"
OUTPUT_BUCKET = "appleforge-athena-query-results"
SEASON = 2024

# In the Lambda zip, SQL files are bundled at doubleday/sql/. Locally, they
# live at the project root under sql/pipeline/. Resolve to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SQL_DIR = PROJECT_ROOT / "sql"


def _get_bucket_name(suffix: str) -> str:
    """Resolve a dev bucket name by listing S3 buckets matching a suffix."""
    response = s3_client.list_buckets()
    for bucket in response["Buckets"]:
        name: str = bucket["Name"]
        if "doubleday" in name and "dev" in name and suffix in name:
            return name
    pytest.fail(f"No dev bucket found matching *doubleday*dev*{suffix}*")
    return ""  # unreachable, satisfies type checker


def _athena_query(sql: str) -> str:
    """Submit a query to Athena and wait for completion."""
    result: str = run_query(athena_client, sql, DATABASE, OUTPUT_BUCKET)
    return result


def _s3_get_json(bucket: str, key: str) -> dict:
    """Download and parse a JSON object from S3."""
    resp = s3_client.get_object(Bucket=bucket, Key=key)
    result: dict = json.loads(resp["Body"].read())
    return result


@pytest.mark.integration
class TestExtractPlayerIds:
    """Test player ID extraction from silver_pitches via Athena."""

    def test_extracts_pitchers(self):
        """Extract pitcher IDs for season 2024 and verify non-empty results."""
        rows = extract_player_ids(
            athena_client,
            DATABASE,
            OUTPUT_BUCKET,
            SQL_DIR,
            SEASON,
            "pitchers",
        )

        assert len(rows) > 0
        assert "player_id" in rows[0]
        assert "team_abbr" in rows[0]
        # Player IDs should be numeric strings
        assert rows[0]["player_id"].isdigit()

    def test_extracts_batters(self):
        """Extract batter IDs for season 2024 and verify non-empty results."""
        rows = extract_player_ids(
            athena_client,
            DATABASE,
            OUTPUT_BUCKET,
            SQL_DIR,
            SEASON,
            "batters",
        )

        assert len(rows) > 0
        assert rows[0]["player_id"].isdigit()


@pytest.mark.integration
class TestExtractCoverage:
    """Test coverage date extraction from silver_pitches via Athena."""

    def test_returns_date_bounds(self):
        """Extract coverage for season 2024 and verify date bounds."""
        coverage = extract_coverage(
            athena_client,
            DATABASE,
            OUTPUT_BUCKET,
            SQL_DIR,
            SEASON,
        )

        assert coverage["first_game_date"] != ""
        assert coverage["last_game_date"] != ""
        assert coverage["first_game_date"] <= coverage["last_game_date"]


@pytest.mark.integration
class TestBuildCatalogForRole:
    """Test the full catalog build pipeline end-to-end.

    Calls build_catalog_for_role with real AWS clients and the MLB Stats API,
    then verifies the result and published S3 artifacts.
    """

    @pytest.fixture()
    def lakehouse_bucket(self):
        """Resolve the dev lakehouse bucket name."""
        return _get_bucket_name("lakehouse")

    @pytest.fixture()
    def frontend_bucket(self):
        """Resolve the dev frontend bucket name."""
        return _get_bucket_name("frontend")

    def test_builds_pitcher_catalog(self, lakehouse_bucket, frontend_bucket):
        """Build pitcher catalog for season 2024 and verify result and artifacts."""
        result = build_catalog_for_role(
            athena_client,
            s3_client,
            DATABASE,
            OUTPUT_BUCKET,
            lakehouse_bucket,
            frontend_bucket,
            SQL_DIR,
            SEASON,
            "pitchers",
        )

        # Verify result
        assert isinstance(result, CatalogBuildResult)
        assert result.season == SEASON
        assert result.role == "pitchers"
        assert result.player_count > 0
        assert result.team_count > 0
        assert result.catalog_bytes > 0
        assert result.enrichment_missing >= 0

        # Verify catalog.json artifact
        catalog = _s3_get_json(
            frontend_bucket,
            f"static/catalogs/pitchers/season={SEASON}/catalog.json",
        )
        assert catalog["schema_version"] == 1
        assert catalog["season"] == SEASON
        assert catalog["role"] == "pitchers"
        assert len(catalog["players"]) == result.player_count
        assert len(catalog["teams"]) == result.team_count

        # Verify player records have required fields
        player = catalog["players"][0]
        assert "id" in player
        assert "first" in player
        assert "last" in player
        assert "last_norm" in player
        assert "headshot_url" in player

        # Verify manifest.json artifact
        manifest = _s3_get_json(
            frontend_bucket,
            f"static/catalogs/pitchers/season={SEASON}/manifest.json",
        )
        assert manifest["schema_version"] == 1
        assert manifest["counts"]["players"] == result.player_count
        assert manifest["catalog"]["bytes"] == result.catalog_bytes
        assert manifest["catalog"]["etag"].startswith('"')

    def test_enrichment_cache_persisted(self, lakehouse_bucket, frontend_bucket):
        """After a build, the enrichment cache exists in the lakehouse bucket."""
        build_catalog_for_role(
            athena_client,
            s3_client,
            DATABASE,
            OUTPUT_BUCKET,
            lakehouse_bucket,
            frontend_bucket,
            SQL_DIR,
            SEASON,
            "pitchers",
        )

        cache = load_enrichment_cache(s3_client, lakehouse_bucket)

        assert len(cache) > 0
        # Cache entries should have enrichment fields
        sample = next(iter(cache.values()))
        assert "first" in sample
        assert "last" in sample
