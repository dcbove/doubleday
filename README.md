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

## Data Lake

Bronze (raw CSV) → Silver (typed Iceberg) → Gold (aggregated Iceberg) → DynamoDB (serving). Dimension tables (teams, venues, games, umpires, players) enrich the pitch data with MLB API metadata.

See [DATALAKE.md](docs/DATALAKE.md) for table definitions, storage layout, and Iceberg details.

## Pipeline

A Standard Step Function orchestrates the full ETL: bronze download → silver load → dimension load → gold aggregation → DynamoDB serving.

See [PIPELINE.md](docs/PIPELINE.md) for Step Function flow, Lambda functions, and data processing details. See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for design rationale (partition overwrite vs MERGE, Standard vs Express Step Functions, etc.).

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
