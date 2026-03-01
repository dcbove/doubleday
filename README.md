# Doubleday

Analysis and processing of pitch-by-pitch MLB data sourced from Baseball Savant's Statcast system.

## Setup

```bash
brew install pyenv uv node
pyenv install 3.13

git clone <repo-url> doubleday
cd doubleday
make install
```

`make install` installs Python dependencies, frontend dependencies, and configures the pre-commit hook (see [Pre-commit hooks](#pre-commit-hooks)).

## Project structure

```
src/doubleday/
  pipeline/
    validate_input/
      handler.py        # Lambda entry point — validate input, generate batch_id
    bronze_load/
      handler.py        # Lambda entry point — event parsing, metrics, response
      pipeline.py       # Business logic — download from Baseball Savant to S3
    silver_load/
      handler.py        # Lambda entry point — event parsing, metrics, response
      pipeline.py       # Business logic — stage, validate, replace pipeline
    gold_load/
      handler.py        # Lambda entry point — event parsing, metrics, response
      pipeline.py       # Business logic — partition overwrite pipeline
    clear_staging/
      handler.py        # Lambda entry point — bulk delete staging rows by batch_id
    check_failures/
      handler.py        # Lambda entry point — read silver load failure records from S3
  api/
    query_pitches/
      handler.py        # API Gateway proxy handler — pitcher pitch-shape stats
      query.py          # Business logic — Athena query + result formatting
    authorizer/
      handler.py        # TOKEN authorizer — validate Cognito JWT tokens
  util/
    athena.py           # Shared Athena query execution utilities
  main.py               # CLI entry point
sql/
  ddl/
    silver_pitches.sql                                # Iceberg DDL (canonical)
    silver_pitches_staging.sql                        # Iceberg DDL (staging)
    gold_pitches_shape_season.sql                     # Iceberg DDL (pitch shape aggs)
    gold_pitch_type_norm_stats.sql                    # Iceberg DDL (pitch type norms)
    gold_repertoire_shape_neighbors.sql               # Iceberg DDL (similarity neighbors)
  pipeline/
    silver_load_partition_into_staging_table.sql       # Bronze -> staging INSERT
    silver_validate_staging_table.sql                  # Duplicate key check on staging
    silver_delete_partition_from_canonical_table.sql   # Delete partition from canonical
    silver_insert_partition_into_canonical_table.sql   # Staging -> canonical INSERT
    silver_clear_partition_from_staging_table.sql      # Bulk delete staging by batch_id
    gold_pitches_shape_season_delete.sql              # Delete gold partition
    gold_pitches_shape_season_insert.sql              # INSERT from silver
    gold_pitch_type_norm_stats_delete.sql             # Delete norm stats
    gold_pitch_type_norm_stats_insert.sql             # INSERT from shape season
    gold_repertoire_shape_neighbors_delete.sql        # Delete neighbors
    gold_repertoire_shape_neighbors_insert.sql        # INSERT from norm stats + shape season
  api/
    query_pitches.sql                                 # SELECT pitcher pitch-shape stats
terraform/
  modules/
    doubleday/          # Composition module — wires all child modules, builds shared Lambda zip
    pipeline/
      s3/               # Lakehouse bucket
      glue/             # Database and table DDL (bronze, silver, gold)
      lambda/           # Pipeline Lambda functions, IAM
      step_function/    # Pipeline Step Function, IAM, logging
    api/                # API Gateway, query Lambda, authorizer Lambda, custom domain
    frontend/           # S3 bucket, CloudFront distribution, OAC, domain
    cognito/            # Cognito user pool with Google federation
    oidc/               # GitHub Actions OIDC provider and IAM role
  environments/
    dev/                # Dev environment root (doubleday + oidc modules)
    prod/               # Prod environment root (doubleday module only)
.github/workflows/
  terraform-plan.yml    # PR: apply dev + plan prod
  terraform-apply.yml   # Merge to main: apply prod
tests/
  unit/
    test_main.py                            # Main module unit tests
    api/
      test_authorizer_handler.py            # API authorizer unit tests
      test_query_pitches_query.py            # API query pitches unit tests
    pipeline/
      test_bronze_load_pipeline.py          # Bronze load unit tests
      test_clear_staging_handler.py         # Clear staging unit tests
      test_gold_load_pipeline.py            # Gold load unit tests
      test_silver_load_pipeline.py          # Silver load unit tests
      test_validate_input_handler.py        # Validate input unit tests
    util/
      test_athena.py                        # Athena utility unit tests
  integration/
    test_silver_pitches_load.py             # Silver load integration tests
    api/
      test_query_pitches_synthetic.py       # API integration — synthetic Lambda events
      test_query_pitches_gateway.py         # API integration — test-invoke-method (no auth)
      test_query_pitches_auth.py            # API integration — end-to-end HTTPS with auth
frontend/
  app/                      # Expo Router file-based routes
    _layout.jsx             # Root: AuthProvider, fonts, global CSS
    index.jsx               # Landing (public login)
    callback.jsx            # OAuth callback handler
    (auth)/                 # Protected route group
      _layout.jsx           # Shell: Navbar + content area
      dashboard.jsx         # Search home
      pitchers/
        [id].jsx            # Pitcher detail
        [idA]/
          compare.jsx       # Pitcher compare
  src/
    auth/
      amplifyConfig.js      # Platform-aware Amplify config (EXPO_PUBLIC_* env vars)
      AuthProvider.jsx       # React Context: user state, login, logout, getAccessToken
      useAuth.js             # useContext(AuthContext) hook
    api/
      client.js             # Platform-aware fetch wrapper with Bearer token
    components/
      Navbar.jsx            # Top nav bar
      PlayerSearch.jsx      # Typeahead search with FlatList results
      SearchInput.jsx       # Styled TextInput with loading/clear
      PlayerResult.jsx      # Search result row
      PitchMovementChart.jsx      # react-native-svg scatter plot
      PitchStatsTable.jsx         # Stats table (ScrollView-based)
      SimilarPitchersList.jsx     # Similar pitchers list
      CompareMovementChart.jsx    # Overlay comparison chart
      CompareStatsTable.jsx       # Side-by-side comparison table
    hooks/
      useCatalog.js         # Catalog fetch + AsyncStorage cache
      usePitchData.js       # Pitch stats API hook
      useNeighborData.js    # Similar pitchers API hook
      catalogCache.js       # AsyncStorage cache helpers
      normalizeQuery.js     # Search query normalization
    util/
      pitchTypes.js         # Pitch type colors and names
  package.json              # Expo SDK 54, NativeWind v4, react-native-svg, Amplify v6
  app.json                  # Expo config (scheme, plugins)
  babel.config.js           # babel-preset-expo + NativeWind
  metro.config.js           # Metro + NativeWind CSS interop
  tailwind.config.js        # NativeWind/Tailwind config
  global.css                # Tailwind directives
  eas.json                  # EAS Build profiles
scripts/
  download_year.sh      # Download Statcast CSVs from Baseball Savant
```

Handler code (`handler.py`) is separated from business logic (`pipeline.py`) so the pipeline can be tested and reused without a Lambda runtime. Shared utilities like Athena query execution live in `src/doubleday/util/` for use across Lambdas and tests.

## Development

```bash
make test               # Run unit tests (excludes integration)
make test-integration   # Run integration tests (requires AWS credentials)
make lint               # Lint and auto-fix with ruff
make format             # Format with black
make typecheck          # Type check with mypy
make check-all          # Run all checks (lint, format, typecheck, unit tests)
make frontend-dev       # Start frontend web dev server (http://localhost:8081)
make frontend-ios       # Build and run on iOS simulator
make frontend-build     # Build frontend for production (web)
```

### Pre-commit hooks

The pre-commit hook auto-fixes lint and formatting issues (via `ruff --fix` and `black`), re-stages the changes, then fails only on errors that can't be auto-fixed (type errors, test failures). Installed automatically by `make install`, or manually:

```bash
make install-hooks
```

This sets `core.hooksPath` to `.githooks/`, which is tracked in the repo — no extra tooling needed.

### Code standards

- All Python modules, public functions, classes, and methods must have docstrings (Google-style convention).
- Linting: ruff (`B`, `D`, `E`, `F`, `I`, `UP` rules). Formatting: black. Type checking: mypy.
- See `CLAUDE.md` for AI-assisted development guidelines.

## Data: Bronze Layer

The bronze layer is raw, unmodified Statcast pitch-by-pitch CSV data downloaded from Baseball Savant. All columns are stored as strings. Data is Hive-style partitioned by season and game date for use with Athena and Glue.

### Local layout

```
data/bronze/
└── season=2025/
    ├── game_date=2025-03-01/statcast.csv
    ├── game_date=2025-03-02/statcast.csv
    └── ...
```

## Data: Silver Layer

The silver layer is the canonical, typed source of truth for all game types (regular season, postseason, spring training, etc.). Data is stored as Apache Iceberg tables in Parquet format, partitioned by `(season, game_date)`. Deprecated columns from the bronze layer are dropped and all remaining columns are strongly typed.

### Tables

- **`silver_pitches`** — canonical pitch-by-pitch table. Partitioned by `(season, game_date)`. Each load replaces the full partition via DELETE + INSERT.
- **`silver_pitches_staging`** — transient scratch table with the same schema plus `run_id` and `batch_id` columns. Used to stage one day's data at a time before replacing canonical.

### Table creation

Tables are created via Athena DDL, triggered automatically by `terraform apply` through `null_resource` provisioners. The SQL definitions live in:

```
sql/ddl/silver_pitches.sql
sql/ddl/silver_pitches_staging.sql
```

Schema evolution (adding columns, changing types) should be done via Athena `ALTER TABLE` statements, not by modifying the Glue catalog directly — Iceberg manages its own metadata in S3.

### Silver load pipeline

The `silver_load` Lambda loads a single `(season, game_date)` partition from bronze to silver. The pipeline runs these steps in order:

1. **Load partition** — INSERT from `bronze_statcast` into `silver_pitches_staging` with type casting, tagged with `run_id` and `batch_id`
2. **Validate staging** — check for duplicate `(game_pk, at_bat_number, pitch_number)` keys; fail before canonical write if any found
3. **Delete canonical** — DELETE the partition from `silver_pitches`
4. **Insert canonical** — INSERT from staging into `silver_pitches`

If validation fails, the canonical table is untouched. Staging cleanup is handled separately by the `clear_staging` Lambda after all silver loads complete (see [Pipeline Orchestration](#pipeline-orchestration)).

### Isolation: `run_id` and `batch_id`

Each staging row is tagged with two identifiers:

- **`run_id`** (per-Lambda, UUID) — isolates each Lambda invocation's rows within staging. Validate and insert queries filter by `run_id`, so concurrent Lambda invocations on different partitions never interfere with each other in staging.
- **`batch_id`** (per-Step Function execution, UUID) — groups all staging rows from one pipeline execution. The `clear_staging` Lambda uses `batch_id` to bulk-delete all staging data in a single query after the silver load map completes.

**Concurrency constraint:** the DELETE + INSERT into canonical is not atomic. Two concurrent executions writing to the same `(season, game_date)` partition could interleave and produce duplicates. The Step Function ensures each partition is processed by exactly one Lambda within an execution. Overlapping executions on the same partition are an operational concern — don't run two backfills that overlap on the same dates concurrently.

### S3 layout

```
s3://doubleday-<env>-lakehouse/silver/
├── silver_pitches/            # Iceberg data + metadata
└── silver_pitches_staging/    # Iceberg data + metadata
```

## Data: Gold Layer

The gold layer contains precomputed analytical tables built from silver. Each table is an Iceberg table partitioned by `season` and loaded via partition overwrite (DELETE + INSERT). Gold tables are rebuilt from scratch whenever the pipeline runs — there is no incremental merge.

### Tables

- **`gold_pitches_shape_season`** — per-pitcher, per-pitch-type season aggregations including movement, velocity, spin, and usage metrics. Regular season games only (`game_type = 'R'`). Minimum 20-pitch threshold per pitch type.
- **`gold_pitch_type_norm_stats`** — per-pitch-type normalization statistics (mean/stddev for velocity and movement) across all history. Used to z-score features for similarity calculations. Depends on `gold_pitches_shape_season`.
- **`gold_repertoire_shape_neighbors`** — top-N cross-season repertoire shape similarity neighbors per pitcher-season profile. Depends on `gold_pitch_type_norm_stats`.

### Table creation

Tables are created via Athena DDL, triggered by `terraform apply`:

```
sql/ddl/gold_pitches_shape_season.sql
sql/ddl/gold_pitch_type_norm_stats.sql
sql/ddl/gold_repertoire_shape_neighbors.sql
```

### Gold load pipeline

The `gold_load` Lambda loads a single gold table for a given season. It reads a pair of SQL files — a DELETE (clear the season partition) and an INSERT (rebuild from silver) — and executes each in order. Tables that need additional SQL template parameters (beyond `season`) receive them via `format_params` in the event payload.

### S3 layout

```
s3://doubleday-<env>-lakehouse/gold/
├── gold_pitches_shape_season/           # Iceberg data + metadata
├── gold_pitch_type_norm_stats/          # Iceberg data + metadata
└── gold_repertoire_shape_neighbors/     # Iceberg data + metadata
```

## Data: Serving Layer (DynamoDB)

The serving layer is a DynamoDB single-table (`doubleday-{env}-serving`) populated from gold Iceberg tables. It provides single-digit millisecond reads for the API, replacing Athena queries. Items use composite keys: `PK = PITCHER#{id}#SEASON#{year}`, `SK = PITCH#{type}` or `NEIGHBOR#{rank:03d}`.

The `dynamodb_load` Lambda reads a gold table via Athena, deletes existing items for that entity/season, then batch-writes fresh items. Both entity types run automatically as a parallel step in the pipeline after gold load completes.

## Player Catalogs

The catalog build pipeline generates static player catalog artifacts (`catalog.json` and `manifest.json`) for each season and role. These are published to the frontend S3 bucket and served via CloudFront. The SPA fetches the manifest through the authenticated API, then conditionally downloads the catalog blob for local search.

### S3 layout

```
s3://doubleday-<env>-frontend/static/catalogs/
├── pitchers/
│   └── season=2024/
│       ├── catalog.json      # Full player catalog blob
│       └── manifest.json     # Metadata: etag, coverage, counts
└── batters/
    └── season=2024/
        ├── catalog.json
        └── manifest.json
```

## Pipeline Orchestration

A Standard Step Function orchestrates the full ETL pipeline:

1. **ValidateInput** — validate all game_date years match season, default `force_download` to `false`, generate `batch_id`
2. **BronzeLoadMap** (concurrency 5) — invoke `bronze_load` for each date (download from Baseball Savant to S3)
3. **SilverLoadMap** (concurrency 5) — invoke `silver_load` for each date, passing `batch_id`. Individual failures are caught and recorded to S3 (`failures/silver_load/{batch_id}/{game_date}.json`); the map continues processing remaining dates.
4. **ClearStaging** — invoke `clear_staging` to bulk-delete all staging rows for this `batch_id`
5. **GoldLoadShapeSeason** — invoke `gold_load` for `gold_pitches_shape_season`
6. **GoldLoadNormStats** — invoke `gold_load` for `gold_pitch_type_norm_stats` (depends on shape season)
7. **GoldLoadNeighbors** — invoke `gold_load` for `gold_repertoire_shape_neighbors` (depends on norm stats)
8. **DynamoDBLoadParallel** — invoke `dynamodb_load` for pitches and neighbors concurrently
9. **CatalogBuildMap** (concurrency 2) — invoke `catalog_build` for each role (pitchers, batters)
10. **CheckFailures** — invoke `check_failures` to scan S3 for failure records from this `batch_id`
11. **HasFailures** — if any silver loads failed, the execution ends with `SilverLoadPartialFailure`; otherwise succeeds

See [OPERATIONS.md](docs/OPERATIONS.md) for Lambda invocation commands, scripts, and operational runbooks. See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for design rationale (partition overwrite vs MERGE, Standard vs Express Step Functions, etc.).

## Frontend

Expo React Native app targeting iOS, Android, and web from a single codebase. Served from S3 via CloudFront at `https://doubleday-<env>.appleforge.com` (web). Authenticates users via Cognito (Google federation) using Amplify v6 PKCE flow.

### Architecture

```
Web Browser → CloudFront (doubleday-<env>.appleforge.com)
                ├── /*       → S3 origin (static SPA assets, OAC)
                └── /api/*   → CF Function (strip /api) → API Gateway (api.doubleday-<env>.appleforge.com)
                                                            x-api-key injected as custom origin header

Mobile App → API Gateway (api.doubleday-<env>.appleforge.com)
               x-api-key sent directly by the app
```

### Local development

Create `frontend/.env` with your Cognito and API key values:

```bash
# From: cd terraform/environments/dev && terraform output
EXPO_PUBLIC_COGNITO_USER_POOL_ID=<cognito_user_pool_id>
EXPO_PUBLIC_COGNITO_CLIENT_ID=<cognito_client_id>
EXPO_PUBLIC_COGNITO_DOMAIN=doubleday-dev
EXPO_PUBLIC_COGNITO_REGION=us-east-1
EXPO_PUBLIC_REDIRECT_SIGN_IN=http://localhost:8081/callback
EXPO_PUBLIC_REDIRECT_SIGN_OUT=http://localhost:8081
EXPO_PUBLIC_API_URL=https://doubleday-dev.appleforge.com/api
EXPO_PUBLIC_CDN_ORIGIN=https://doubleday-dev.appleforge.com
EXPO_PUBLIC_API_KEY=<api_key>
```

```bash
make frontend-dev       # Web: http://localhost:8081
make frontend-ios       # iOS simulator (requires Xcode)
```

Web dev uses the deployed CloudFront backend (`EXPO_PUBLIC_API_URL` and `EXPO_PUBLIC_CDN_ORIGIN`). In production, these env vars are omitted so the app uses same-origin `/api` and relative static paths.

## Testing

See [TESTING.md](docs/TESTING.md) for unit tests, integration tests, and integration test setup.

## REST API

See [API.md](docs/API.md) for endpoints, authentication, rate limiting, and OpenAPI spec.

## Operations

See [OPERATIONS.md](docs/OPERATIONS.md) for Lambda invocation commands, scripts, and operational runbooks.

## iOS Release

See [RELEASE.md](docs/RELEASE.md) for building and distributing iOS releases (device testing, TestFlight, App Store).

## Infrastructure & Deployment

See [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for Terraform modules, CI/CD workflows, and bootstrap setup.
