"""Catalog build pipeline — extract player IDs, enrich, and publish catalog artifacts.

Produces static player catalog artifacts for a single (season, role) pair:

1. **Extract** distinct player IDs and their last-seen team from silver_pitches
   via Athena.
2. **Enrich** each player with metadata (name, position, bats/throws, current
   team, headshot URL) from the MLB Stats API, falling back to a persistent
   enrichment cache for last-known-good semantics.
3. **Build** a catalog.json (the searchable dataset) and manifest.json (change-
   detection metadata) conforming to the schema_version 1 contract defined in
   typeahead.md.
4. **Publish** both artifacts to the frontend S3 bucket at deterministic paths
   served by CloudFront.

The main entry point is ``build_catalog_for_role``, called by the Lambda handler.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aws_lambda_powertools import Logger

from doubleday.util.athena import get_query_results, run_query
from doubleday.util.mlb import fetch_players, fetch_teams, normalize_name

logger = Logger(child=True)

SQL_FILES = {
    "pitchers": "pipeline/catalog_extract_pitchers.sql",
    "batters": "pipeline/catalog_extract_batters.sql",
}

ENRICHMENT_CACHE_KEY = "catalogs/enrichment_cache.json"


def load_sql(sql_dir: Path, filename: str) -> str:
    """Read a SQL template from the given directory."""
    return (sql_dir / filename).read_text()


@dataclass
class CatalogBuildResult:
    """Result of a catalog build pipeline run.

    Attributes:
        season: MLB season year that was built.
        role: Player role that was built ("pitchers" or "batters").
        player_count: Number of players included in the catalog (excludes
            players with no enrichment data).
        team_count: Number of distinct teams referenced in the catalog.
        catalog_bytes: Size of the serialized catalog.json in bytes.
        enrichment_cache_hit: Players whose enrichment came from cache
            (API did not return them).
        enrichment_api_hit: Players whose enrichment came from the MLB API.
        enrichment_missing: Players excluded because neither the API nor
            the cache had enrichment data for them.
        last_known_good: True if any player's enrichment was served from
            cache because the API did not return them.
    """

    season: int
    role: str
    player_count: int
    team_count: int
    catalog_bytes: int
    enrichment_cache_hit: int
    enrichment_api_hit: int
    enrichment_missing: int
    last_known_good: bool


def extract_player_ids(
    athena,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    season: int,
    role: str,
) -> list[dict[str, str]]:
    """Extract distinct player IDs and last-seen teams from silver_pitches.

    Selects the SQL template based on role (``catalog_extract_pitchers.sql``
    or ``catalog_extract_batters.sql``), formats it with the season, and
    executes it via Athena. Each row represents one player with the team
    they were last seen on in that season (determined by most recent pitch
    event).

    Args:
        athena: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        sql_dir: Path to SQL template directory.
        season: MLB season year.
        role: Player role ("pitchers" or "batters").

    Returns:
        List of dicts with ``player_id`` (string) and ``team_abbr`` keys.
    """
    sql_file = SQL_FILES[role]
    sql = load_sql(sql_dir, sql_file).format(season=season)
    logger.info("Extracting player IDs", extra={"role": role, "sql_file": sql_file})
    execution_id = run_query(athena, sql, database, output_bucket)
    return get_query_results(athena, execution_id)


def extract_coverage(
    athena,
    database: str,
    output_bucket: str,
    sql_dir: Path,
    season: int,
) -> dict[str, str]:
    """Query the min and max game_date in silver_pitches for the season.

    The returned date bounds appear in the manifest as ``coverage`` fields,
    telling the SPA how much of the season has been ingested so far. This
    supports mid-season messaging (e.g. "data through May 14").

    Args:
        athena: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        sql_dir: Path to SQL template directory.
        season: MLB season year.

    Returns:
        Dict with ``first_game_date`` and ``last_game_date`` keys (strings).
        Both are empty strings if no data exists for the season.
    """
    sql = load_sql(sql_dir, "pipeline/catalog_coverage.sql").format(season=season)
    logger.info("Extracting coverage", extra={"season": season})
    execution_id = run_query(athena, sql, database, output_bucket)
    rows = get_query_results(athena, execution_id)
    if rows:
        return rows[0]
    return {"first_game_date": "", "last_game_date": ""}


def load_enrichment_cache(s3, bucket: str) -> dict[str, dict]:
    """Load the global enrichment cache from the lakehouse bucket.

    The cache is a single JSON file shared across all roles and seasons
    (player metadata is role-agnostic). It maps string player IDs to their
    most recently fetched enrichment fields. On the first run the file
    will not exist; this is normal and returns an empty dict.

    Args:
        s3: Boto3 S3 client.
        bucket: Lakehouse S3 bucket name.

    Returns:
        Dict mapping player ID strings to enrichment dicts.
        Empty dict if the cache file does not exist yet.

    Raises:
        ClientError: For S3 errors other than NoSuchKey (e.g. access denied).
    """
    try:
        resp = s3.get_object(Bucket=bucket, Key=ENRICHMENT_CACHE_KEY)
        result: dict[str, dict] = json.loads(resp["Body"].read())
        return result
    except s3.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            logger.info("No enrichment cache found, starting fresh")
            return {}
        raise


def save_enrichment_cache(s3, bucket: str, cache: dict[str, dict]) -> None:
    """Persist the enrichment cache to the lakehouse bucket.

    Overwrites the existing cache file. The caller is responsible for
    merging new enrichment data into the cache dict before calling this.

    Args:
        s3: Boto3 S3 client.
        bucket: Lakehouse S3 bucket name.
        cache: Enrichment cache dict to persist (string keys → enrichment dicts).
    """
    body = json.dumps(cache, separators=(",", ":")).encode()
    s3.put_object(Bucket=bucket, Key=ENRICHMENT_CACHE_KEY, Body=body)
    logger.info("Saved enrichment cache", extra={"entries": len(cache)})


def resolve_enrichment(
    player_ids: list[int],
    cache: dict[str, dict],
    *,
    force_rebuild: bool = False,
) -> tuple[dict[int, dict], bool, int, int]:
    """Enrich player IDs, fetching from the API only when needed.

    In incremental mode (default), players already present in the cache are
    reused without an API call. Only players missing from the cache are
    fetched. In force-rebuild mode, the API is called for every player and
    the cache is used only as a last-known-good fallback when the API misses
    a player.

    Args:
        player_ids: List of MLBAM player IDs to enrich.
        cache: Existing enrichment cache (string keys → enrichment dicts).
        force_rebuild: When True, fetch all players from the API regardless
            of cache state.

    Returns:
        Tuple of (merged enrichment dict keyed by int player ID,
        last_known_good flag, api_hit count, cache_hit count).
    """
    if force_rebuild:
        ids_to_fetch = player_ids
    else:
        ids_to_fetch = [pid for pid in player_ids if str(pid) not in cache]

    api_results = fetch_players(ids_to_fetch) if ids_to_fetch else {}
    merged: dict[int, dict] = {}
    last_known_good = False
    api_hit = 0
    cache_hit = 0

    for pid in player_ids:
        pid_str = str(pid)
        if pid in api_results:
            enrichment = api_results[pid]
            merged[pid] = {
                "first": enrichment.first_name,
                "last": enrichment.last_name,
                "bats": enrichment.bats,
                "throws": enrichment.throws,
                "pos": enrichment.position,
                "current_team_id": enrichment.current_team_id,
            }
            api_hit += 1
        elif pid_str in cache:
            merged[pid] = cache[pid_str]
            cache_hit += 1
            if pid in set(ids_to_fetch):
                # We tried to fetch but the API missed this player
                last_known_good = True
        # else: player has no enrichment, will be excluded

    return merged, last_known_good, api_hit, cache_hit


def build_catalog(
    season: int,
    role: str,
    players: list[dict],
    teams: dict[str, dict],
) -> dict:
    """Assemble the catalog.json artifact dict.

    Players are sorted by (last name, first name) for stable ordering in
    the SPA's default player list view. The teams dict uses string keys
    (e.g. ``"147"``) to avoid JSON numeric-key inconsistencies.

    See typeahead.md "catalog.json" for the full schema contract.

    Args:
        season: MLB season year.
        role: Player role ("pitchers" or "batters").
        players: List of player dicts with all fields populated.
        teams: Dict mapping string team ID to team info dict (abbr, name).

    Returns:
        Catalog dict with schema_version, season, role, teams, and players.
    """
    sorted_players = sorted(players, key=lambda p: (p["last"], p["first"]))
    return {
        "schema_version": 1,
        "season": season,
        "role": role,
        "teams": teams,
        "players": sorted_players,
    }


def build_manifest(
    season: int,
    role: str,
    coverage: dict[str, str],
    catalog_bytes: int,
    player_count: int,
    team_count: int,
    last_known_good: bool,
) -> dict:
    """Assemble the manifest.json artifact dict.

    The manifest is a small file the SPA fetches via the authenticated API
    to decide whether to re-download the catalog blob. It includes an etag
    for change detection, byte count for progress indication, and coverage
    bounds for mid-season messaging.

    See typeahead.md "manifest.json" for the full schema contract.

    Args:
        season: MLB season year.
        role: Player role ("pitchers" or "batters").
        coverage: Dict with first_game_date and last_game_date from Athena.
        catalog_bytes: Size of the serialized catalog.json in bytes.
        player_count: Number of players in the catalog.
        team_count: Number of teams referenced in the catalog.
        last_known_good: Whether any player's enrichment was served from
            cache rather than the live API.

    Returns:
        Manifest dict with schema_version, season, role, generated_at,
        coverage, counts, catalog (url/etag/bytes), and enrichment metadata.
    """
    now = datetime.now(tz=UTC)
    catalog_url = f"/static/catalogs/{role}/season={season}/catalog.json"
    etag = hashlib.md5(str(catalog_bytes).encode() + now.isoformat().encode()).hexdigest()  # noqa: S324

    return {
        "schema_version": 1,
        "season": season,
        "role": role,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {
            "first_game_date_seen": coverage.get("first_game_date", ""),
            "last_game_date_seen": coverage.get("last_game_date", ""),
        },
        "counts": {"players": player_count, "teams": team_count},
        "catalog": {
            "url": catalog_url,
            "etag": f'"{etag}"',
            "bytes": catalog_bytes,
        },
        "enrichment": {
            "as_of": now.strftime("%Y-%m-%d"),
            "last_known_good": last_known_good,
        },
    }


def publish_artifacts(
    s3,
    bucket: str,
    season: int,
    role: str,
    catalog_body: bytes,
    manifest: dict,
) -> None:
    """Write catalog.json and manifest.json to the frontend S3 bucket.

    Artifacts are written to deterministic paths under
    ``static/catalogs/{role}/season={YYYY}/``. CloudFront serves these
    directly from S3 — URIs with a ``.json`` extension bypass the SPA
    routing function.

    The catalog is written first, then the manifest, so a client that reads
    the manifest will always find the catalog it references.

    Args:
        s3: Boto3 S3 client.
        bucket: Frontend S3 bucket name.
        season: MLB season year.
        role: Player role ("pitchers" or "batters").
        catalog_body: Pre-serialized catalog JSON bytes.
        manifest: Manifest dict to serialize and upload.
    """
    prefix = f"static/catalogs/{role}/season={season}"

    s3.put_object(
        Bucket=bucket,
        Key=f"{prefix}/catalog.json",
        Body=catalog_body,
        ContentType="application/json",
    )
    logger.info("Published catalog", extra={"key": f"{prefix}/catalog.json"})

    manifest_body = json.dumps(manifest, separators=(",", ":")).encode()
    s3.put_object(
        Bucket=bucket,
        Key=f"{prefix}/manifest.json",
        Body=manifest_body,
        ContentType="application/json",
    )
    logger.info("Published manifest", extra={"key": f"{prefix}/manifest.json"})


def build_catalog_for_role(
    athena,
    s3,
    database: str,
    output_bucket: str,
    lakehouse_bucket: str,
    frontend_bucket: str,
    sql_dir: Path,
    season: int,
    role: str,
    *,
    force_rebuild: bool = False,
) -> CatalogBuildResult:
    """Build and publish the catalog for a single season and role.

    This is the main orchestrator called by the Lambda handler. It runs the
    full pipeline end-to-end:

    1. Extract player IDs and last-seen teams from silver_pitches (Athena).
    2. Extract coverage date bounds from silver_pitches (Athena).
    3. Load the enrichment cache from the lakehouse bucket.
    4. Fetch the MLB teams lookup (abbreviation → team ID).
    5. Resolve enrichment: in incremental mode (default), only fetch players
       not already in the cache; in force-rebuild mode, re-fetch all.
    6. Save the updated enrichment cache.
    7. Merge silver data (player_id, team_season_id) with enrichment
       (name, bats/throws, position, team_current_id, headshot).
    8. Exclude players with no enrichment (unusable in search).
    9. Build the catalog dict, serialize to JSON.
    10. Build the manifest dict.
    11. Publish both artifacts to the frontend S3 bucket.

    Args:
        athena: Boto3 Athena client.
        s3: Boto3 S3 client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        lakehouse_bucket: S3 bucket for the enrichment cache.
        frontend_bucket: S3 bucket for the published catalog artifacts.
        sql_dir: Path to SQL template directory.
        season: MLB season year.
        role: Player role ("pitchers" or "batters").
        force_rebuild: When True, re-fetch all players from the MLB API
            regardless of cache state. Defaults to False (incremental).

    Returns:
        CatalogBuildResult with player/team counts, byte size, enrichment
        hit/miss statistics, and whether last-known-good semantics were used.
    """
    # 1. Extract player IDs and team abbreviations from silver
    silver_rows = extract_player_ids(athena, database, output_bucket, sql_dir, season, role)
    logger.info("Extracted player IDs", extra={"count": len(silver_rows)})

    # 2. Extract coverage date bounds
    coverage = extract_coverage(athena, database, output_bucket, sql_dir, season)
    logger.info("Extracted coverage", extra={"coverage": coverage})

    # 3. Load enrichment cache
    cache = load_enrichment_cache(s3, lakehouse_bucket)

    # 4. Fetch teams
    teams_lookup = fetch_teams()

    # 5. Resolve enrichment (incremental by default, force_rebuild re-fetches all)
    all_player_ids = [int(row["player_id"]) for row in silver_rows]
    enrichment, last_known_good, enrichment_api_hit, enrichment_cache_hit = resolve_enrichment(
        all_player_ids, cache, force_rebuild=force_rebuild
    )

    # 6. Update and save enrichment cache
    for pid, data in enrichment.items():
        cache[str(pid)] = data
    save_enrichment_cache(s3, lakehouse_bucket, cache)

    # 7. Build player records by merging silver + enrichment + teams
    # Build a lookup from silver: player_id -> team_abbr
    silver_teams = {int(row["player_id"]): row["team_abbr"] for row in silver_rows}

    # Collect all referenced team IDs for the teams dict
    catalog_teams: dict[str, dict] = {}
    players: list[dict] = []
    enrichment_missing = 0

    for pid in all_player_ids:
        if pid not in enrichment:
            enrichment_missing += 1
            continue

        data = enrichment[pid]

        # Determine team_season_id from silver team_abbr
        team_abbr = silver_teams.get(pid, "")
        team_season_info = teams_lookup.get(team_abbr)
        team_season_id = team_season_info.team_id if team_season_info else None

        # Current team from enrichment
        team_current_id = data.get("current_team_id")

        # Add referenced teams to catalog teams dict
        if team_season_id is not None:
            tid_str = str(team_season_id)
            if tid_str not in catalog_teams and team_season_info:
                catalog_teams[tid_str] = {
                    "abbr": team_season_info.abbreviation,
                    "name": team_season_info.team_name,
                }

        if team_current_id is not None:
            tid_str = str(team_current_id)
            if tid_str not in catalog_teams:
                # Find team info by ID
                for tinfo in teams_lookup.values():
                    if tinfo.team_id == team_current_id:
                        catalog_teams[tid_str] = {
                            "abbr": tinfo.abbreviation,
                            "name": tinfo.team_name,
                        }
                        break

        player_record = {
            "id": pid,
            "first": data["first"],
            "last": data["last"],
            "last_norm": normalize_name(data["last"]),
            "bats": data.get("bats", ""),
            "throws": data.get("throws", ""),
            "pos": data.get("pos", ""),
            "team_season_id": team_season_id,
            "team_current_id": team_current_id,
            "headshot_url": f"https://img.mlbstatic.com/mlb-photos/image/upload"
            f"/d_people:generic:headshot:67:current.png"
            f"/w_213,q_auto:best/v1/people/{pid}/headshot/67/current",
        }
        players.append(player_record)

    # 9. Build catalog
    catalog = build_catalog(season, role, players, catalog_teams)

    # 10. Serialize
    catalog_body = json.dumps(catalog, separators=(",", ":")).encode()

    # 11. Build manifest
    manifest = build_manifest(
        season,
        role,
        coverage,
        len(catalog_body),
        len(players),
        len(catalog_teams),
        last_known_good,
    )

    # 12. Publish
    publish_artifacts(s3, frontend_bucket, season, role, catalog_body, manifest)

    return CatalogBuildResult(
        season=season,
        role=role,
        player_count=len(players),
        team_count=len(catalog_teams),
        catalog_bytes=len(catalog_body),
        enrichment_cache_hit=enrichment_cache_hit,
        enrichment_api_hit=enrichment_api_hit,
        enrichment_missing=enrichment_missing,
        last_known_good=last_known_good,
    )
