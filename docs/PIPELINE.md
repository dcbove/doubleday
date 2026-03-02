# Pipeline

Step Function orchestration, Lambda functions, and data flow for the Doubleday ETL pipeline. For data model and table definitions, see [DATALAKE.md](DATALAKE.md). For project overview, see [README.md](../README.md).

## Step Function Flow

A Standard Step Function orchestrates the full ETL pipeline:

```
ValidateInput → BronzeLoadMap → SilverLoadMap → ClearStaging
→ DimensionLoadParallel [teams, venues, games, umpires, players]
→ GoldLoadShapeSeason → GoldLoadNormStats → GoldLoadNeighbors → GoldLoadCatalog
→ DynamoDBLoadParallel [pitches, neighbors, catalog]
→ CheckFailures → Done
```

1. **ValidateInput** — validate all `game_date` years match `season`, default `force_download` to `false`, generate `batch_id`
2. **BronzeLoadMap** (concurrency 5) — invoke `bronze_load` for each date (download from Baseball Savant to S3)
3. **SilverLoadMap** (concurrency 5) — invoke `silver_load` for each date, passing `batch_id`. Individual failures are caught and recorded to S3 (`failures/silver_load/{batch_id}/{game_date}.json`); the map continues processing remaining dates.
4. **ClearStaging** — invoke `clear_staging` to bulk-delete all staging rows for this `batch_id`
5. **DimensionLoadParallel** — invoke `dimension_load` for all five dimensions concurrently (teams, venues, games, umpires, players). Games, umpires, and players receive `game_dates` for date-scoped loading.
6. **GoldLoadShapeSeason** — invoke `gold_load` for `gold_pitches_shape_season`
7. **GoldLoadNormStats** — invoke `gold_load` for `gold_pitch_type_norm_stats` (depends on shape season)
8. **GoldLoadNeighbors** — invoke `gold_load` for `gold_repertoire_shape_neighbors` (depends on norm stats)
9. **GoldLoadCatalog** — invoke `gold_load` for `gold_catalog` (depends on silver pitches, players, and teams)
10. **DynamoDBLoadParallel** — invoke `dynamodb_load` for pitches, neighbors, and catalog concurrently
11. **CheckFailures** — scan S3 for failure records from this `batch_id`. If any silver loads failed, the execution ends with `SilverLoadPartialFailure`; otherwise succeeds.

## Lambda Functions

| Lambda | Module | Description |
|--------|--------|-------------|
| `validate_input` | `pipeline/validate_input/` | Validate event, generate `batch_id` |
| `bronze_load` | `pipeline/bronze_load/` | Download Statcast CSV from Baseball Savant to S3 |
| `silver_load` | `pipeline/silver_load/` | Stage, validate, replace pitch partition (bronze → silver) |
| `clear_staging` | `pipeline/clear_staging/` | Bulk-delete staging rows by `batch_id` |
| `dimension_load` | `pipeline/dimension_load/` | Two-phase dimension load (MLB API → bronze cache → silver) |
| `gold_load` | `pipeline/gold_load/` | Parameterized gold table rebuild (DELETE + INSERT from SQL templates) |
| `dynamodb_load` | `pipeline/dynamodb_load/` | Load gold table data into DynamoDB serving table |
| `check_failures` | `pipeline/check_failures/` | Scan S3 for silver load failure records |

## Silver Load Pipeline

The `silver_load` Lambda loads a single `(season, game_date)` partition from bronze to silver. Steps run in order:

1. **Load partition** — INSERT from `bronze_statcast` into `silver_pitches_staging` with type casting, tagged with `run_id` and `batch_id`
2. **Validate staging** — check for duplicate `(game_pk, at_bat_number, pitch_number)` keys; fail before canonical write if any found
3. **Delete canonical** — DELETE the partition from `silver_pitches`
4. **Insert canonical** — INSERT from staging into `silver_pitches`

If validation fails, the canonical table is untouched. Staging cleanup is handled separately by the `clear_staging` Lambda after all silver loads complete.

### Isolation: `run_id` and `batch_id`

Each staging row is tagged with two identifiers:

- **`run_id`** (per-Lambda, UUID) — isolates each Lambda invocation's rows within staging. Validate and insert queries filter by `run_id`, so concurrent Lambda invocations on different partitions never interfere with each other in staging.
- **`batch_id`** (per-Step Function execution, UUID) — groups all staging rows from one pipeline execution. The `clear_staging` Lambda uses `batch_id` to bulk-delete all staging data in a single query after the silver load map completes.

**Concurrency constraint:** the DELETE + INSERT into canonical is not atomic. Two concurrent executions writing to the same `(season, game_date)` partition could interleave and produce duplicates. The Step Function ensures each partition is processed by exactly one Lambda within an execution. Overlapping executions on the same partition are an operational concern — don't run two backfills that overlap on the same dates concurrently.

## Dimension Load Pipeline

The `dimension_load` Lambda loads a single dimension table per invocation. The Step Function invokes it once per dimension per pipeline run, with all five dimensions running in parallel.

Each dimension follows a two-phase pattern:

1. **Bronze phase** — check S3 for cached JSON. If missing (or `force_download=true`), fetch from the MLB API, write to bronze. On subsequent runs the API is not re-called.
2. **Silver phase** — DELETE the partition, INSERT INTO ... VALUES from the bronze data.

### Per-dimension behavior

| Dimension | Source | Caching | Rows/season |
|-----------|--------|---------|-------------|
| teams | `fetch_teams_for_season(season)` | Snapshot — full season cache | ~30 |
| venues | Venue IDs from teams bronze → `fetch_venues(ids)` | Snapshot — full season cache | ~30 |
| games | `fetch_schedule(date)` for each `game_date` | Snapshot — one bronze file per date | ~15/date |
| umpires | IDs from `silver_games` → `fetch_umpires(ids)` | Additive — only fetches new IDs | ~100 |
| players | IDs from `silver_pitches` → `fetch_players(ids)` | Additive — only fetches new IDs | ~1,000 |

**Snapshot vs additive caching**: Teams, venues, and games are fetched entirely from the MLB API — the bronze cache is all-or-nothing. Umpires and players are discovered incrementally — umpires from `silver_games` (HP umpire IDs) and players from `silver_pitches` (pitcher/batter IDs). Their bronze caches are dicts keyed by ID. On each run, the loader queries the source table for IDs, diffs against the cache, fetches only new IDs from the API, and merges them into the cache. When `game_dates` is provided, the source queries are scoped to those dates for faster incremental runs.

**Player `current_team_id` retention**: The MLB API returns `currentTeam=null` during offseason, spring training, DFA windows, and minor league assignments. When merging fresh API data into the bronze cache, the loader retains the previous `current_team_id` value when the API returns None. This ensures the catalog always reflects the last known team.

**Season-scope rebuilds**: Teams, venues, umpires, and players replace the full season partition on every run. Since data is cached in bronze, this is cheap — no API calls after the first run, just a few small Athena queries.

**Games are incremental**: Only the `game_dates` passed in the event are deleted and re-inserted, with one bronze file per date.

## Gold Load Pipeline

The `gold_load` Lambda loads a single gold table for a given season. It reads a pair of SQL files — `{table_name}_delete.sql` (clear the season partition) and `{table_name}_insert.sql` (rebuild from silver) — and executes each in order. Tables that need additional SQL template parameters (beyond `season`) receive them via `format_params` in the event payload.

Gold tables are rebuilt in dependency order (shape season → norm stats → neighbors). Adding a new gold table means adding two SQL files and a Step Function entry — no Lambda code changes.

## DynamoDB Load

The `dynamodb_load` Lambda reads a gold table via Athena, deletes existing DynamoDB items for that entity/season, then batch-writes fresh items. Entity-specific configuration (SQL file, PK/SK builders, number columns) is declared in `ENTITY_CONFIG` — adding a new entity type requires no structural changes.

## Backfills

To process an entire season (March 1-Nov 30), use the backfill script:

```bash
bash scripts/backfill_season.sh 2024        # defaults to dev
bash scripts/backfill_season.sh 2024 prod   # specify environment
```

This generates all ~275 dates in the range and starts a single Step Function execution. Bronze load skips any dates already in S3 (unless `force_download` is set), so backfills are safe to re-run — only silver and gold do real work for previously downloaded data. Dimension bronze caches also make backfills cheap: once teams/venues/games have been fetched for a season, subsequent runs read from S3.
