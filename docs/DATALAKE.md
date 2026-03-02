# Data Lake

Data model, storage layout, and table definitions for the Doubleday lakehouse. For pipeline orchestration and data flow, see [PIPELINE.md](PIPELINE.md). For project overview, see [README.md](../README.md).

## Storage

All data lives in a single S3 bucket (`doubleday-{env}-lakehouse`) organized by layer:

```
s3://doubleday-<env>-lakehouse/
├── bronze/                       # Raw Statcast CSVs (Glue external table)
├── bronze_dimensions/            # Dimension JSON caches (not in Glue)
├── silver/                       # Typed Iceberg tables
│   ├── silver_pitches/
│   ├── silver_pitches_staging/
│   ├── silver_teams/
│   ├── silver_venues/
│   ├── silver_games/
│   ├── silver_umpires/
│   └── silver_players/
└── gold/                         # Analytical Iceberg tables
    ├── gold_pitches_shape_season/
    ├── gold_pitch_type_norm_stats/
    ├── gold_repertoire_shape_neighbors/
    └── gold_catalog/
```

All silver and gold tables are Apache Iceberg with Parquet storage. Table DDL lives in `sql/ddl/` and is applied automatically by `terraform apply` via `null_resource` provisioners. Schema evolution (adding columns, changing types) should be done via Athena `ALTER TABLE` statements, not by modifying the Glue catalog directly — Iceberg manages its own metadata in S3.

## Bronze Layer

The bronze layer stores raw, unmodified source data. There are two categories:

### Statcast pitches

Raw pitch-by-pitch CSV data downloaded from Baseball Savant. All columns are stored as strings. Data is Hive-style partitioned by season and game date, registered as a Glue external table (`bronze_statcast`) with partition projection.

```
bronze/
└── season=2025/
    ├── game_date=2025-03-01/statcast.csv
    ├── game_date=2025-03-02/statcast.csv
    └── ...
```

The same layout is used locally (`data/bronze/`) for development and manual downloads.

### Dimension caches

Parsed JSON from MLB API calls, cached in S3 so backfills replay from local storage without re-fetching. Not registered as Glue tables — read directly by the `dimension_load` Lambda via the S3 API.

```
bronze_dimensions/
├── teams/season=2025/data.json
├── venues/season=2025/data.json
├── games/season=2025/
│   ├── game_date=2025-03-01/data.json
│   └── game_date=2025-03-02/data.json
├── umpires/season=2025/data.json
└── players/season=2025/data.json
```

Two caching strategies:
- **Snapshot** (teams, venues, games): JSON array, all-or-nothing cache. If present, the entire file is reused.
- **Additive** (umpires, players): JSON dict keyed by ID. New IDs discovered in `silver_pitches` are fetched from the API and merged into the existing cache. Existing entries are never re-fetched (unless `force_download=true`).

## Silver Layer

The silver layer is the canonical, typed source of truth. All game types are included (regular season, postseason, spring training, etc.). Deprecated columns from the bronze layer are dropped and all remaining columns are strongly typed.

### Pitch tables

| Table | Partition | Description |
|-------|-----------|-------------|
| `silver_pitches` | `(season, game_date)` | Canonical pitch-by-pitch table. Each load replaces the full partition via DELETE + INSERT. |
| `silver_pitches_staging` | `(season, game_date)` | Transient scratch table with the same schema plus `run_id` and `batch_id` columns. Used to stage data before replacing canonical. |

DDL: `sql/ddl/silver_pitches.sql`, `sql/ddl/silver_pitches_staging.sql`

### Dimension tables

| Table | Partition | Description |
|-------|-----------|-------------|
| `silver_teams` | `season` | MLB teams — ID, abbreviation, full name, league, division, venue, active status. ~30 rows per season. |
| `silver_venues` | `season` | MLB venues — name, address, city/state, lat/long, elevation. ~30 rows per season. |
| `silver_games` | `season` | Games — game_pk, type, date, venue, teams, scores, home plate umpire. ~2,400 rows per season. |
| `silver_umpires` | `season` | Home plate umpires — ID and full name. ~100 rows per season. |
| `silver_players` | `season` | Players — name, handedness, position, current team, headshot URL. ~1,000 rows per season. |

DDL: `sql/ddl/silver_teams.sql`, `sql/ddl/silver_venues.sql`, `sql/ddl/silver_games.sql`, `sql/ddl/silver_umpires.sql`, `sql/ddl/silver_players.sql`

Dimension tables are loaded by a dedicated `dimension_load` Lambda (not the `silver_load` Lambda used for pitches). See [PIPELINE.md](PIPELINE.md) for the loading process.

## Gold Layer

The gold layer contains precomputed analytical tables built from silver. Each table is partitioned by `season` and loaded via partition overwrite (DELETE + INSERT). Gold tables are rebuilt from scratch whenever the pipeline runs — there is no incremental merge.

| Table | Depends On | Description |
|-------|-----------|-------------|
| `gold_pitches_shape_season` | `silver_pitches` | Per-pitcher, per-pitch-type season aggregations (movement, velocity, spin, usage). Regular season only (`game_type = 'R'`), minimum 20-pitch threshold. |
| `gold_pitch_type_norm_stats` | `gold_pitches_shape_season` | Per-pitch-type normalization statistics (mean/stddev for velocity and movement). Used to z-score features for similarity calculations. |
| `gold_repertoire_shape_neighbors` | `gold_pitch_type_norm_stats`, `gold_pitches_shape_season` | Top-N cross-season repertoire shape similarity neighbors per pitcher-season profile. |
| `gold_catalog` | `silver_pitches`, `silver_players`, `silver_teams` | Denormalized player catalog with team info for API serving. One row per player per role (pitcher/batter). |

DDL: `sql/ddl/gold_pitches_shape_season.sql`, `sql/ddl/gold_pitch_type_norm_stats.sql`, `sql/ddl/gold_repertoire_shape_neighbors.sql`, `sql/ddl/gold_catalog.sql`

SQL templates: each gold table has a pair of pipeline SQL files (`{table_name}_delete.sql` and `{table_name}_insert.sql`) in `sql/pipeline/`.

## Serving Layer (DynamoDB)

A single DynamoDB table (`doubleday-{env}-serving`) is populated from gold Iceberg tables to provide single-digit millisecond reads for the API. Items use composite keys:

| Entity | PK | SK |
|--------|----|----|
| Pitches | `PITCHER#{id}#SEASON#{year}` | `PITCH#{type}` |
| Neighbors | `PITCHER#{id}#SEASON#{year}` | `NEIGHBOR#{rank:03d}` |
| Catalog | `CATALOG#{role}#SEASON#{year}` | `PLAYER#{player_id}` |

The `dynamodb_load` Lambda reads a gold table via Athena, deletes existing items for that entity/season, then batch-writes fresh items. All three entity types run automatically as a parallel step in the pipeline after gold load completes.

## Iceberg Introspection

View snapshot history (each load creates a new snapshot):

```sql
SELECT * FROM "silver_pitches$snapshots";
```

Verify partition pruning is working on a query:

```sql
EXPLAIN
SELECT COUNT(*)
FROM silver_pitches
WHERE season = 2025
  AND game_date = DATE '2025-05-14';
```
