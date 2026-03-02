"""Dimension load pipeline — two-phase bronze cache + silver load for dimension tables.

Each dimension follows the same pattern:
1. Bronze phase: check S3 cache, fetch from MLB API if missing, write JSON to bronze.
2. Silver phase: DELETE partition → INSERT INTO ... VALUES from the bronze data.

This mirrors the pitch pipeline (bronze_load → silver_load) but both phases happen
in a single Lambda invocation since dimension data volumes are small (~30-1000 rows).
"""

import json
from dataclasses import dataclass
from typing import Any

from aws_lambda_powertools import Logger

from doubleday.util.athena import get_query_results, run_query
from doubleday.util.mlb import (
    PlayerEnrichment,
    fetch_players,
    fetch_schedule,
    fetch_teams_for_season,
    fetch_umpires,
    fetch_venues,
    normalize_name,
)
from doubleday.util.sql import build_values_insert

logger = Logger(child=True)


@dataclass
class DimensionLoadResult:
    """Result of a dimension load operation.

    Attributes:
        records_loaded: Number of rows inserted into the silver table.
        bronze_cached: Whether bronze data was read from cache (True) or
            fetched fresh from the MLB API (False).
    """

    records_loaded: int
    bronze_cached: bool


# ---------------------------------------------------------------------------
# Bronze S3 helpers
# ---------------------------------------------------------------------------


def _bronze_key(dimension: str, season: int, game_date: str | None = None) -> str:
    """Build the S3 key for a bronze dimension cache file.

    Args:
        dimension: Dimension name (teams, venues, games, umpires, players).
        season: Season year.
        game_date: Optional game date for per-date dimensions (games).

    Returns:
        S3 object key for the bronze JSON file.
    """
    if game_date:
        return f"bronze_dimensions/{dimension}/season={season}/game_date={game_date}/data.json"
    return f"bronze_dimensions/{dimension}/season={season}/data.json"


def _bronze_exists(s3_client, bucket: str, key: str) -> bool:
    """Check if a bronze cache file exists in S3.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        True if the object exists, False otherwise.
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except s3_client.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise
    return True


def _read_bronze_json(s3_client, bucket: str, key: str) -> Any:
    """Read a bronze JSON cache file from S3.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        Parsed JSON — either a list (snapshot dimensions) or a dict
        (additive dimensions keyed by ID).
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def _write_bronze_json(s3_client, bucket: str, key: str, data: list | dict) -> None:
    """Write a bronze JSON cache file to S3.

    Args:
        s3_client: Boto3 S3 client.
        bucket: S3 bucket name.
        key: S3 object key.
        data: JSON-serializable data (list or dict).
    """
    body = json.dumps(data, ensure_ascii=False)
    s3_client.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))


# ---------------------------------------------------------------------------
# Silver load helpers
# ---------------------------------------------------------------------------


def _delete_partition(athena_client, database: str, output_bucket: str, table: str, where_clause: str) -> str:
    """Delete a partition from a silver dimension table.

    Args:
        athena_client: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        table: Silver table name.
        where_clause: SQL WHERE clause (without the WHERE keyword).

    Returns:
        Athena query execution ID.
    """
    sql = f"DELETE FROM {table} WHERE {where_clause}"
    logger.info("Deleting partition", extra={"table": table, "where": where_clause})
    return run_query(athena_client, sql, database, output_bucket)


def _insert_rows(
    athena_client,
    database: str,
    output_bucket: str,
    table: str,
    columns: list[str],
    rows: list[dict],
) -> int:
    """Insert rows into a silver dimension table via batched VALUES statements.

    Args:
        athena_client: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        table: Silver table name.
        columns: Ordered list of column names.
        rows: List of dicts to insert.

    Returns:
        Total number of rows inserted.
    """
    statements = build_values_insert(table, columns, rows)
    total = 0
    for i, sql in enumerate(statements):
        logger.info(
            "Inserting batch",
            extra={"table": table, "batch": i + 1, "total_batches": len(statements)},
        )
        run_query(athena_client, sql, database, output_bucket)
        total += min(100, len(rows) - i * 100)
    return total


# ---------------------------------------------------------------------------
# Per-dimension loaders
# ---------------------------------------------------------------------------

TEAMS_COLUMNS = [
    "team_id",
    "abbreviation",
    "team_name",
    "full_name",
    "league_id",
    "league_name",
    "division_id",
    "division_name",
    "venue_id",
    "active",
    "season",
]


def _fetch_teams_bronze(season: int) -> list[dict]:
    """Fetch teams from MLB API and return as bronze-format dicts.

    Args:
        season: Season year.

    Returns:
        List of dicts with column names matching silver_teams.
    """
    teams = fetch_teams_for_season(season)
    return [
        {
            "team_id": t.team_id,
            "abbreviation": t.abbreviation,
            "team_name": t.team_name,
            "full_name": t.full_name,
            "league_id": t.league_id,
            "league_name": t.league_name,
            "division_id": t.division_id,
            "division_name": t.division_name,
            "venue_id": t.venue_id,
            "active": t.active,
            "season": season,
        }
        for t in teams
    ]


def _load_teams(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    season: int,
    force_download: bool,
) -> DimensionLoadResult:
    """Load teams dimension: bronze fetch/cache → silver INSERT.

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        force_download: If True, re-fetch from API even if bronze exists.

    Returns:
        DimensionLoadResult with records loaded and cache status.
    """
    key = _bronze_key("teams", season)
    cached = False

    if not force_download and _bronze_exists(s3_client, bucket, key):
        logger.info("Teams bronze cache hit", extra={"key": key})
        rows = _read_bronze_json(s3_client, bucket, key)
        cached = True
    else:
        logger.info("Fetching teams from MLB API", extra={"season": season})
        rows = _fetch_teams_bronze(season)
        _write_bronze_json(s3_client, bucket, key, rows)

    if not rows:
        return DimensionLoadResult(records_loaded=0, bronze_cached=cached)

    _delete_partition(athena_client, database, output_bucket, "silver_teams", f"season = {season}")
    total = _insert_rows(athena_client, database, output_bucket, "silver_teams", TEAMS_COLUMNS, rows)
    return DimensionLoadResult(records_loaded=total, bronze_cached=cached)


VENUES_COLUMNS = [
    "venue_id",
    "name",
    "address1",
    "city",
    "state",
    "state_abbrev",
    "postal_code",
    "latitude",
    "longitude",
    "elevation",
    "country",
    "season",
]


def _fetch_venues_bronze(s3_client, bucket: str, season: int) -> list[dict]:
    """Fetch venues from MLB API using venue IDs from teams bronze.

    Reads the teams bronze cache to get venue_ids, deduplicates, then fetches
    venue metadata from the MLB API.

    Args:
        s3_client: Boto3 S3 client.
        bucket: Lakehouse S3 bucket name.
        season: Season year.

    Returns:
        List of dicts with column names matching silver_venues.
    """
    teams_key = _bronze_key("teams", season)
    teams_data = _read_bronze_json(s3_client, bucket, teams_key)
    venue_ids = sorted({t["venue_id"] for t in teams_data if t.get("venue_id") is not None})
    logger.info("Fetching venues from MLB API", extra={"count": len(venue_ids)})

    venues = fetch_venues(venue_ids)
    return [
        {
            "venue_id": v.venue_id,
            "name": v.name,
            "address1": v.address1,
            "city": v.city,
            "state": v.state,
            "state_abbrev": v.state_abbrev,
            "postal_code": v.postal_code,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "elevation": v.elevation,
            "country": v.country,
            "season": season,
        }
        for v in venues
    ]


def _load_venues(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    season: int,
    force_download: bool,
) -> DimensionLoadResult:
    """Load venues dimension: bronze fetch/cache → silver INSERT.

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        force_download: If True, re-fetch from API even if bronze exists.

    Returns:
        DimensionLoadResult with records loaded and cache status.
    """
    key = _bronze_key("venues", season)
    cached = False

    if not force_download and _bronze_exists(s3_client, bucket, key):
        logger.info("Venues bronze cache hit", extra={"key": key})
        rows = _read_bronze_json(s3_client, bucket, key)
        cached = True
    else:
        rows = _fetch_venues_bronze(s3_client, bucket, season)
        _write_bronze_json(s3_client, bucket, key, rows)

    if not rows:
        return DimensionLoadResult(records_loaded=0, bronze_cached=cached)

    _delete_partition(athena_client, database, output_bucket, "silver_venues", f"season = {season}")
    total = _insert_rows(athena_client, database, output_bucket, "silver_venues", VENUES_COLUMNS, rows)
    return DimensionLoadResult(records_loaded=total, bronze_cached=cached)


GAMES_COLUMNS = [
    "game_pk",
    "game_type",
    "game_date",
    "official_date",
    "venue_id",
    "day_night",
    "away_team_id",
    "home_team_id",
    "away_score",
    "home_score",
    "hp_umpire_id",
    "hp_umpire_name",
    "season",
]


def _fetch_games_bronze(game_date: str) -> list[dict]:
    """Fetch games from MLB API for a single date.

    Args:
        game_date: Date in YYYY-MM-DD format.

    Returns:
        List of dicts with column names matching silver_games.
    """
    games = fetch_schedule(game_date)
    return [
        {
            "game_pk": g.game_pk,
            "game_type": g.game_type,
            "game_date": g.game_date,
            "official_date": g.official_date,
            "venue_id": g.venue_id,
            "day_night": g.day_night,
            "away_team_id": g.away_team_id,
            "home_team_id": g.home_team_id,
            "away_score": g.away_score,
            "home_score": g.home_score,
            "hp_umpire_id": g.hp_umpire_id,
            "hp_umpire_name": g.hp_umpire_name,
            "season": g.season,
        }
        for g in games
    ]


def _load_games(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    season: int,
    game_dates: list[str],
    force_download: bool,
) -> DimensionLoadResult:
    """Load games dimension: bronze fetch/cache per date → silver INSERT.

    Games use per-date bronze caching since the schedule API is date-scoped.

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        game_dates: List of date strings in YYYY-MM-DD format.
        force_download: If True, re-fetch from API even if bronze exists.

    Returns:
        DimensionLoadResult with records loaded and cache status.
    """
    all_rows: list[dict] = []
    any_cached = False
    all_cached = True

    for game_date in game_dates:
        key = _bronze_key("games", season, game_date)

        if not force_download and _bronze_exists(s3_client, bucket, key):
            logger.info("Games bronze cache hit", extra={"key": key})
            rows = _read_bronze_json(s3_client, bucket, key)
            any_cached = True
        else:
            logger.info("Fetching games from MLB API", extra={"date": game_date})
            rows = _fetch_games_bronze(game_date)
            _write_bronze_json(s3_client, bucket, key, rows)
            all_cached = False

        all_rows.extend(rows)

    if not all_rows:
        return DimensionLoadResult(records_loaded=0, bronze_cached=any_cached)

    # Deduplicate by game_pk. Postponed/suspended games can appear under
    # multiple dates from the schedule API. Keep the row with scores (the
    # completed game); if both have scores, keep the later game_date.
    seen: dict[int, dict] = {}
    for row in all_rows:
        gpk = row["game_pk"]
        existing = seen.get(gpk)
        if existing is None:
            seen[gpk] = row
        else:
            row_has_scores = bool(row.get("away_score") or row.get("home_score"))
            existing_has_scores = bool(existing.get("away_score") or existing.get("home_score"))
            if row_has_scores and not existing_has_scores:
                seen[gpk] = row
            elif row_has_scores and existing_has_scores:
                if row.get("game_date", "") > existing.get("game_date", ""):
                    seen[gpk] = row

    deduped = list(seen.values())
    if len(deduped) < len(all_rows):
        logger.info(
            "Deduplicated games by game_pk",
            extra={"before": len(all_rows), "after": len(deduped)},
        )
    all_rows = deduped

    # Delete only the dates we're loading
    dates_str = ", ".join(f"'{d}'" for d in game_dates)
    where = f"season = {season} AND official_date IN ({dates_str})"
    _delete_partition(athena_client, database, output_bucket, "silver_games", where)
    total = _insert_rows(athena_client, database, output_bucket, "silver_games", GAMES_COLUMNS, all_rows)
    return DimensionLoadResult(records_loaded=total, bronze_cached=all_cached and any_cached)


UMPIRES_COLUMNS = ["umpire_id", "full_name", "season"]


def _get_umpire_ids_from_games(
    athena_client,
    database: str,
    output_bucket: str,
    season: int,
    game_dates: list[str] | None = None,
) -> list[int]:
    """Query silver_games for distinct home plate umpire IDs.

    When ``game_dates`` is provided, only games on those dates are queried.
    This keeps the query fast during incremental pipeline runs. The bronze
    cache accumulates across runs, so the full season is still represented
    in silver after the INSERT phase.

    Args:
        athena_client: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        game_dates: Optional list of date strings to scope the query.

    Returns:
        Sorted list of umpire IDs.
    """
    sql = f"SELECT DISTINCT hp_umpire_id FROM silver_games WHERE season = {season} AND hp_umpire_id IS NOT NULL"
    if game_dates:
        dates_str = ", ".join(f"'{d}'" for d in game_dates)
        sql += f" AND official_date IN ({dates_str})"
    execution_id = run_query(athena_client, sql, database, output_bucket)
    rows = get_query_results(athena_client, execution_id)
    return sorted(int(row["hp_umpire_id"]) for row in rows)


def _load_umpires(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    season: int,
    game_dates: list[str] | None,
    force_download: bool,
) -> DimensionLoadResult:
    """Load umpires dimension with additive bronze caching.

    Unlike snapshot dimensions (teams, venues), umpires are discovered
    incrementally from silver_games. The bronze cache is a dict keyed by
    umpire ID so new umpires can be added without re-fetching existing ones.

    When ``game_dates`` is provided, only umpires from those dates are
    queried from silver_games. New IDs are merged into the bronze cache,
    and the silver table is rebuilt from the full cache.

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        game_dates: Optional list of date strings to scope the query.
        force_download: If True, re-fetch all IDs from API.

    Returns:
        DimensionLoadResult with records loaded and cache status.
    """
    current_ids = _get_umpire_ids_from_games(athena_client, database, output_bucket, season, game_dates)
    if not current_ids:
        return DimensionLoadResult(records_loaded=0, bronze_cached=False)

    key = _bronze_key("umpires", season)

    # Load existing bronze cache (dict keyed by ID string)
    cache: dict[str, dict] = {}
    if _bronze_exists(s3_client, bucket, key):
        cache = _read_bronze_json(s3_client, bucket, key)

    # Find IDs not yet in cache
    if force_download:
        new_ids = current_ids
    else:
        new_ids = [uid for uid in current_ids if str(uid) not in cache]

    # Fetch new umpires from MLB API
    if new_ids:
        logger.info("Fetching new umpires from MLB API", extra={"count": len(new_ids)})
        umpires = fetch_umpires(new_ids)
        for u in umpires.values():
            cache[str(u.umpire_id)] = {
                "umpire_id": u.umpire_id,
                "full_name": u.full_name,
                "season": season,
            }
        _write_bronze_json(s3_client, bucket, key, cache)
    else:
        logger.info("All umpire IDs already in bronze cache")

    # Rebuild silver from the full bronze cache (not just current_ids)
    rows = list(cache.values())

    _delete_partition(athena_client, database, output_bucket, "silver_umpires", f"season = {season}")
    total = _insert_rows(athena_client, database, output_bucket, "silver_umpires", UMPIRES_COLUMNS, rows)
    return DimensionLoadResult(records_loaded=total, bronze_cached=not bool(new_ids))


PLAYERS_COLUMNS = [
    "player_id",
    "first_name",
    "last_name",
    "last_norm",
    "bats",
    "throws",
    "position",
    "current_team_id",
    "headshot_url",
    "season",
]


def _get_player_ids_from_pitches(
    athena_client,
    database: str,
    output_bucket: str,
    season: int,
    game_dates: list[str] | None = None,
) -> list[int]:
    """Query silver_pitches for distinct pitcher and batter IDs.

    When ``game_dates`` is provided, only pitches from those dates are
    queried. This keeps the query fast during incremental pipeline runs.
    The bronze cache accumulates across runs, so the full season is still
    represented in silver after the INSERT phase.

    Args:
        athena_client: Boto3 Athena client.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        game_dates: Optional list of date strings to scope the query.

    Returns:
        Sorted list of player IDs.
    """
    date_filter = ""
    if game_dates:
        dates_str = ", ".join(f"DATE '{d}'" for d in game_dates)
        date_filter = f" AND game_date IN ({dates_str})"

    sql = (
        "SELECT DISTINCT player_id FROM ("
        f"  SELECT pitcher AS player_id FROM silver_pitches WHERE season = {season}{date_filter}"
        f"  UNION SELECT batter AS player_id FROM silver_pitches WHERE season = {season}{date_filter}"
        ") t WHERE player_id IS NOT NULL"
    )
    execution_id = run_query(athena_client, sql, database, output_bucket)
    rows = get_query_results(athena_client, execution_id)
    return sorted(int(row["player_id"]) for row in rows)


def _enrichment_to_row(e: PlayerEnrichment, season: int) -> dict:
    """Convert a PlayerEnrichment to a bronze-format dict.

    Args:
        e: PlayerEnrichment from the MLB API.
        season: Season year.

    Returns:
        Dict with column names matching silver_players.
    """
    return {
        "player_id": e.player_id,
        "first_name": e.first_name,
        "last_name": e.last_name,
        "last_norm": normalize_name(e.last_name),
        "bats": e.bats,
        "throws": e.throws,
        "position": e.position,
        "current_team_id": e.current_team_id,
        "headshot_url": e.headshot_url,
        "season": season,
    }


def _retain_current_team_ids(
    bronze_cache: dict[str, dict],
    fresh_rows: dict[str, dict],
) -> None:
    """Retain previous current_team_id when the API returns None.

    The MLB API returns currentTeam=null during offseason, spring training,
    DFA windows, and minor league assignments. When merging fresh API data
    into the bronze cache, if the new data has current_team_id=None but the
    cache has a non-None value, the cached value is retained.

    Operates on the fresh_rows dict in place before it is merged into the cache.

    Args:
        bronze_cache: Existing bronze cache (dict keyed by player ID string).
        fresh_rows: Freshly fetched rows to merge (dict keyed by player ID string).
    """
    retained = 0
    for pid, row in fresh_rows.items():
        if row.get("current_team_id") is None:
            cached = bronze_cache.get(pid, {})
            prev_team = cached.get("current_team_id")
            if prev_team is not None:
                row["current_team_id"] = prev_team
                retained += 1

    if retained:
        logger.info("Retained previous current_team_id", extra={"count": retained})


def _load_players(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    season: int,
    game_dates: list[str] | None,
    force_download: bool,
) -> DimensionLoadResult:
    """Load players dimension with additive bronze caching.

    Like umpires, players are discovered incrementally from silver_pitches.
    The bronze cache is a dict keyed by player ID so new players can be added
    without re-fetching existing ones.

    When ``game_dates`` is provided, only players from those dates are
    queried from silver_pitches. New IDs are merged into the bronze cache,
    and the silver table is rebuilt from the full cache.

    Before merging fresh API data into the cache, retains previous
    current_team_id values when the API returns None (offseason, spring
    training, etc.).

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        season: Season year.
        game_dates: Optional list of date strings to scope the query.
        force_download: If True, re-fetch all IDs from API.

    Returns:
        DimensionLoadResult with records loaded and cache status.
    """
    current_ids = _get_player_ids_from_pitches(athena_client, database, output_bucket, season, game_dates)
    if not current_ids:
        return DimensionLoadResult(records_loaded=0, bronze_cached=False)

    key = _bronze_key("players", season)

    # Load existing bronze cache (dict keyed by ID string)
    cache: dict[str, dict] = {}
    if _bronze_exists(s3_client, bucket, key):
        cache = _read_bronze_json(s3_client, bucket, key)

    # Find IDs not yet in cache
    if force_download:
        new_ids = current_ids
    else:
        new_ids = [pid for pid in current_ids if str(pid) not in cache]

    # Fetch new players from MLB API
    if new_ids:
        logger.info("Fetching new players from MLB API", extra={"count": len(new_ids)})
        enrichments = fetch_players(new_ids)
        fresh_rows = {str(e.player_id): _enrichment_to_row(e, season) for e in enrichments.values()}
        _retain_current_team_ids(cache, fresh_rows)
        cache.update(fresh_rows)
        _write_bronze_json(s3_client, bucket, key, cache)
    else:
        logger.info("All player IDs already in bronze cache")

    # Rebuild silver from the full bronze cache (not just current_ids)
    rows = list(cache.values())

    _delete_partition(athena_client, database, output_bucket, "silver_players", f"season = {season}")
    total = _insert_rows(athena_client, database, output_bucket, "silver_players", PLAYERS_COLUMNS, rows)
    return DimensionLoadResult(records_loaded=total, bronze_cached=not bool(new_ids))


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def load_dimension(
    s3_client,
    athena_client,
    bucket: str,
    database: str,
    output_bucket: str,
    dimension: str,
    season: int,
    game_dates: list[str] | None = None,
    force_download: bool = False,
) -> DimensionLoadResult:
    """Load a single dimension table.

    Dispatches to the appropriate per-dimension loader based on the
    dimension name.

    Args:
        s3_client: Boto3 S3 client.
        athena_client: Boto3 Athena client.
        bucket: Lakehouse S3 bucket name.
        database: Glue database name.
        output_bucket: S3 bucket for Athena query results.
        dimension: One of "teams", "venues", "games", "umpires", "players".
        season: Season year.
        game_dates: List of date strings. Required for "games"; optional
            for "umpires" and "players" to scope incremental queries.
        force_download: If True, re-fetch from API even if bronze exists.

    Returns:
        DimensionLoadResult with records loaded and cache status.

    Raises:
        ValueError: If dimension is not recognized.
    """
    if dimension == "teams":
        return _load_teams(s3_client, athena_client, bucket, database, output_bucket, season, force_download)
    if dimension == "venues":
        return _load_venues(s3_client, athena_client, bucket, database, output_bucket, season, force_download)
    if dimension == "games":
        return _load_games(
            s3_client,
            athena_client,
            bucket,
            database,
            output_bucket,
            season,
            game_dates or [],
            force_download,
        )
    if dimension == "umpires":
        return _load_umpires(
            s3_client,
            athena_client,
            bucket,
            database,
            output_bucket,
            season,
            game_dates,
            force_download,
        )
    if dimension == "players":
        return _load_players(
            s3_client,
            athena_client,
            bucket,
            database,
            output_bucket,
            season,
            game_dates,
            force_download,
        )
    raise ValueError(f"Unknown dimension: {dimension}")
