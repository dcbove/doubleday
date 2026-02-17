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
      pipeline.py       # Business logic — Athena query + result formatting
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
  pipeline/
    silver_load_partition_into_staging_table.sql       # Bronze -> staging INSERT
    silver_validate_staging_table.sql                  # Duplicate key check on staging
    silver_delete_partition_from_canonical_table.sql   # Delete partition from canonical
    silver_insert_partition_into_canonical_table.sql   # Staging -> canonical INSERT
    silver_clear_partition_from_staging_table.sql      # Bulk delete staging by batch_id
    gold_pitches_shape_season_delete.sql              # Delete gold partition
    gold_pitches_shape_season_insert.sql              # INSERT from silver
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
      test_query_pitches_pipeline.py        # API query pitches unit tests
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
  index.html              # Entry HTML
  package.json            # Dependencies: React 19, Vite 6, Tailwind v4, Amplify v6
  vite.config.js          # Dev proxy (/api/* → API Gateway), Tailwind plugin
  src/
    main.jsx              # Entry point, imports Amplify config
    App.jsx               # BrowserRouter + Routes
    index.css             # Tailwind import
    auth/
      amplifyConfig.js    # Amplify.configure() with Cognito PKCE settings
      AuthProvider.jsx    # React Context: user state, login, logout, getAccessToken
      useAuth.js          # useContext(AuthContext) hook
      ProtectedRoute.jsx  # Redirects to / if not authenticated
    api/
      client.js           # fetch wrapper with Bearer token injection
    pages/
      Landing.jsx         # Public: "Sign in with Google" button
      Callback.jsx        # Handles Cognito OAuth redirect
      Dashboard.jsx       # Protected: placeholder
    components/
      Layout.jsx          # App shell with Navbar + content area
      Navbar.jsx          # Logo, nav links, user info, logout button
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
make frontend-dev       # Start frontend dev server (http://localhost:5173)
make frontend-build     # Build frontend for production
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

### Download

```bash
bash scripts/download_year.sh <year>
```

One CSV per day across the MLB season (March through November). Baseball Savant caps exports at ~25,000 rows per request; the script warns if any file hits this limit.

### Local layout

```
data/bronze/
└── season=2025/
    ├── game_date=2025-03-01/statcast.csv
    ├── game_date=2025-03-02/statcast.csv
    └── ...
```

### Invoking the bronze_load Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-bronze-load \
  --payload '{"season": 2024, "game_date": "2024-03-01", "force_download": false}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Sync with S3

```bash
# Upload
aws s3 sync data/bronze/ s3://doubleday-<env>-lakehouse/bronze/

# Download
aws s3 sync s3://doubleday-<env>-lakehouse/bronze/ data/bronze/
```

### Query with Athena

The bronze table is available as `doubleday_<env>.bronze_statcast`. Always filter on partition keys for performance:

```sql
SELECT pitch_type, count(*)
FROM doubleday_dev.bronze_statcast
WHERE season = 2025
GROUP BY pitch_type
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

### Invoking the silver_load Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-silver-load \
  --payload '{"season": 2024, "game_date": "2024-03-01", "batch_id": "manual-test"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

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

### Table creation

Tables are created via Athena DDL, triggered by `terraform apply`:

```
sql/ddl/gold_pitches_shape_season.sql
```

### Gold load pipeline

The `gold_load` Lambda loads a single gold table for a given season. It reads a pair of SQL files — a DELETE (clear the season partition) and an INSERT (rebuild from silver) — and executes each in order.

### Invoking the gold_load Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_pitches_shape_season", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### S3 layout

```
s3://doubleday-<env>-lakehouse/gold/
└── gold_pitches_shape_season/    # Iceberg data + metadata
```

## Pipeline Orchestration

A Standard Step Function orchestrates the full ETL pipeline:

1. **ValidateInput** — validate all game_date years match season, default `force_download` to `false`, generate `batch_id`
2. **BronzeLoadMap** (concurrency 5) — invoke `bronze_load` for each date (download from Baseball Savant to S3)
3. **SilverLoadMap** (concurrency 5) — invoke `silver_load` for each date, passing `batch_id`. Individual failures are caught and recorded to S3 (`failures/silver_load/{batch_id}/{game_date}.json`); the map continues processing remaining dates.
4. **ClearStaging** — invoke `clear_staging` to bulk-delete all staging rows for this `batch_id`
5. **SetGoldTables** — inject hardcoded gold table list
6. **GoldLoadMap** (concurrency 1) — invoke `gold_load` for each table with the season
7. **CheckFailures** — invoke `check_failures` to scan S3 for failure records from this `batch_id`
8. **HasFailures** — if any silver loads failed, the execution ends with `SilverLoadPartialFailure`; otherwise succeeds

### Invoking the Step Function

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:<region>:<account>:stateMachine:doubleday-dev-pipeline \
  --input '{"season": 2024, "game_dates": ["2024-03-01"]}'
```

Use `force_download` to re-download files that already exist in S3:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:<region>:<account>:stateMachine:doubleday-dev-pipeline \
  --input '{"season": 2024, "game_dates": ["2024-03-01"], "force_download": true}'
```

### Backfilling a season

To process an entire season (March 1–Nov 30), use the backfill script:

```bash
bash scripts/backfill_season.sh 2024        # defaults to dev
bash scripts/backfill_season.sh 2024 prod   # specify environment
```

This generates all ~275 dates in the range and starts a single Step Function execution. Bronze load skips any dates already in S3 (unless `force_download` is set), so backfills are safe to re-run — only silver and gold do real work for previously downloaded data.

### Why partition overwrite (DELETE + INSERT) instead of MERGE

Statcast game data is effectively immutable once finalized. Our ingestion unit is already aligned to a natural partition boundary — `(season, game_date)` for silver, `(season)` for gold — and reprocessing means "replace that partition," not "surgically edit individual rows." MERGE (update matched, insert unmatched) would leave behind rows that disappeared from the source — if Statcast retroactively drops a pitch, MERGE can't detect the absence. DELETE + INSERT guarantees canonical exactly mirrors the source for any reprocessed partition.

### Why Standard over Express Step Functions

Standard Step Functions support executions up to one year and have detailed execution history. This matters for backfills — reprocessing an entire season (180+ game dates) can take well over five minutes, which is the Express maximum. Standard also provides per-step visibility in the console, making debugging straightforward.

### Why a single parameterized gold Lambda

One `gold_load` Lambda accepts a table name parameter and executes the corresponding SQL files (`{table_name}_delete.sql` and `{table_name}_insert.sql`). Adding a new gold table means adding two SQL files and a Step Function entry — no Lambda code changes.

### Why the Step Function is the single entry point

All processing flows through the Step Function. There are no S3 event triggers or independent Lambda invocations in production. This eliminates double-processing, makes the pipeline easy to reason about, and gives a single place to monitor execution status.

## REST API

The API provides authenticated access to gold table data. It uses Cognito for authentication (with Google federation) and API Gateway with a custom Lambda authorizer.

### Endpoint

```
GET /pitchers/{pitcher_id}/pitches?season={season}&pitch_type={pitch_type}
```

- `pitcher_id` (path, required): MLB pitcher ID (e.g., `605151`)
- `season` (query, required): Season year (e.g., `2024`)
- `pitch_type` (query, optional): Pitch type filter (e.g., `FF`, `SL`)

Returns pitch-shape stats (movement, velocity, spin, usage) from `gold_pitches_shape_season`.

### Domain layout

- `doubleday-<env>.appleforge.com` — CloudFront serves the SPA and proxies `/api/*` to API Gateway. The `x-api-key` header is injected by CloudFront, so browser clients never need it.
- `api.doubleday-<env>.appleforge.com` — API Gateway directly, for non-browser clients. Requires `x-api-key` header.

### Authentication

1. **Browser**: Sign in via the SPA at `https://doubleday-<env>.appleforge.com` — Cognito OAuth flow with Google federation.

2. **CLI / non-browser**: Include the token and API key:
   ```bash
   curl -H "Authorization: Bearer <token>" \
        -H "x-api-key: <api_key>" \
        "https://api.doubleday-dev.appleforge.com/pitchers/605151/pitches?season=2024"
   ```

### Decoding a JWT

To inspect the claims in a JWT token (useful for debugging auth issues):

```bash
echo "$TOKEN" | cut -d. -f2 | tr '_-' '/+' | awk '{while(length%4)$0=$0"="}1' | base64 -d | python3 -m json.tool
```

Key claims to look for: `token_use` (`id` or `access`), `aud` (id tokens), `client_id` (access tokens), `iss`, `exp`.

### Rate limiting

Requests require an API key (`x-api-key` header) and are subject to rate limiting (default: 50 req/s steady, 100 req/s burst). Browser requests through CloudFront have the API key injected automatically.

## Frontend

React SPA served from S3 via CloudFront at `https://doubleday-<env>.appleforge.com`. Authenticates users via Cognito (Google federation) using Amplify v6 PKCE flow.

### Architecture

```
Browser → CloudFront (doubleday-<env>.appleforge.com)
            ├── /*       → S3 origin (static SPA assets, OAC)
            └── /api/*   → CF Function (strip /api) → API Gateway (api.doubleday-<env>.appleforge.com)
                                                        x-api-key injected as custom origin header
```

### Local development

Create `frontend/.env.local` (gitignored) with your Cognito and API key values:

```bash
# From: cd terraform/environments/dev && terraform output
VITE_COGNITO_USER_POOL_ID=<cognito_user_pool_id>
VITE_COGNITO_CLIENT_ID=<cognito_client_id>
VITE_COGNITO_DOMAIN=doubleday-dev
VITE_COGNITO_REGION=us-east-1
VITE_REDIRECT_SIGN_IN=http://localhost:5173/callback
VITE_REDIRECT_SIGN_OUT=http://localhost:5173
VITE_API_KEY=<api_key>
```

```bash
make frontend-dev       # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `https://api.doubleday-dev.appleforge.com`, strips the `/api` prefix, and injects the `x-api-key` header — mirroring CloudFront behavior in production.

## Testing

### Unit tests

```bash
make test
```

### Integration tests

Integration tests run against live AWS resources in the dev environment. They require valid AWS credentials.

```bash
make test-integration
```

There are three flavors of API integration test:

| Test file | What it exercises | Auth? |
|---|---|---|
| `test_query_pitches_synthetic.py` | Lambda handler directly with synthetic events | No |
| `test_query_pitches_gateway.py` | API Gateway routing via `test-invoke-method` | No (bypassed) |
| `test_query_pitches_auth.py` | Full HTTPS request with Cognito JWT + API key | Yes |

The auth tests (`test_query_pitches_auth.py`) require a test Cognito user and credentials stored in Secrets Manager. See [Integration test setup](#integration-test-setup) for details.

Pipeline integration tests (`test_silver_pitches_load.py`) clear the test partition (`season=2024/game_date=2024-03-01`) from both staging and canonical before running, so they are safe to re-run.

### Integration test setup

The auth integration tests authenticate against a dedicated Cognito test client using `USER_PASSWORD_AUTH`. This requires one-time manual setup after deploying the test client with Terraform:

1. **Deploy the test client** — `terraform apply` in dev (the composition module sets `enable_test_client = true`)

2. **Get IDs from Terraform outputs:**
   ```bash
   USER_POOL_ID=$(cd terraform/environments/dev && terraform output -raw cognito_user_pool_id)
   TEST_CLIENT_ID=$(cd terraform/environments/dev && terraform output -raw cognito_test_client_id)
   API_KEY=$(cd terraform/environments/dev && terraform output -raw api_key)
   ```

3. **Create the test user:**
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id "$USER_POOL_ID" \
     --username "integration-test@doubleday.dev" \
     --user-attributes Name=email,Value=integration-test@doubleday.dev Name=email_verified,Value=true \
     --message-action SUPPRESS

   aws cognito-idp admin-set-user-password \
     --user-pool-id "$USER_POOL_ID" \
     --username "integration-test@doubleday.dev" \
     --password "<your-chosen-password>" \
     --permanent
   ```

4. **Create the Secrets Manager secret:**
   ```bash
   aws secretsmanager create-secret \
     --name "dev/doubleday/cognito_identity_provider/integration_test_credentials" \
     --secret-string '{
       "user_pool_id": "'"$USER_POOL_ID"'",
       "test_client_id": "'"$TEST_CLIENT_ID"'",
       "test_email": "integration-test@doubleday.dev",
       "test_password": "<your-chosen-password>",
       "api_key": "'"$API_KEY"'",
       "api_url": "https://api.doubleday-dev.appleforge.com"
     }'
   ```

The test client is only created in dev (`enable_test_client = true`). Prod defaults to `false` — no test client, no change.

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

## Infrastructure

Infrastructure is managed with Terraform with two environments (dev, prod) in the same AWS account.

```bash
cd terraform/environments/dev   # or prod
terraform init
terraform plan
terraform apply
```

### Modules

| Module | Description |
|--------|-------------|
| `doubleday` | Composition module — wires all child modules, builds the shared Lambda zip |
| `pipeline/s3` | Lakehouse S3 bucket |
| `pipeline/glue` | Glue database, bronze/silver/gold table DDL |
| `pipeline/lambda` | Pipeline Lambda functions (validate_input, bronze_load, silver_load, gold_load, clear_staging), IAM roles |
| `pipeline/step_function` | Pipeline Step Function, IAM role, CloudWatch logging |
| `cognito` | Cognito user pool with Google federation, hosted UI |
| `api` | API Gateway REST API, authorizer Lambda, query Lambda, custom domain, rate limiting |
| `frontend` | S3 bucket (OAC), CloudFront distribution, CF Function, ACM cert, Route53 |
| `oidc` | GitHub Actions OIDC provider and IAM role (dev only, account-level) |

Environment files (`dev/main.tf`, `prod/main.tf`) call `module "doubleday"` and pass variables — they never reference child modules directly. All inter-module wiring lives in the composition module.

All Lambda functions (pipeline and API) share a single deployment zip built by the composition module (`doubleday/package.tf`). It bundles the full `doubleday` Python package from `src/`, SQL templates from `sql/pipeline/` and `sql/api/`, and pip dependencies (PyJWT, cryptography) for the authorizer. Each Lambda points at the same zip with a different handler entry point. Changing any Python, SQL, or dependency triggers a redeployment of all functions, keeping them in sync.

Each API endpoint is a self-contained `.tf` file in the `api` module containing its Lambda function, IAM role, API Gateway resources, and CORS configuration.

## Deployment

Infrastructure changes are deployed automatically via GitHub Actions using OIDC for AWS authentication (no long-lived credentials).

### CI/CD workflows

- **`terraform-plan.yml`** — runs on PRs that touch `terraform/`, `src/`, `sql/`, or `frontend/`. Applies dev (infra + frontend build/deploy) and plans prod (posting the plan as a PR comment).
- **`terraform-apply.yml`** — runs on push to `main` that touches `terraform/`, `src/`, `sql/`, or `frontend/`. Applies prod and deploys the frontend.

Dev is deployed during the PR lifecycle so changes can be tested before merging. Prod is deployed only after merging to `main`.

After Terraform apply, the CI pipeline builds the frontend (`npm run build` with Cognito env vars from Terraform outputs), syncs the dist to S3, and invalidates the CloudFront cache.

### Bootstrap (one-time setup)

The OIDC resources must exist before GitHub Actions can authenticate. To bootstrap:

1. `cd terraform/environments/dev && terraform apply` — creates the OIDC provider and IAM role
2. `cd terraform/environments/prod && terraform apply` — creates prod resources
3. Copy the OIDC role ARN from the `module.oidc.role_arn` output
4. Add it as the GitHub Actions secret `AWS_ROLE_ARN`

After bootstrap, PRs auto-deploy dev and merges to `main` auto-deploy prod.
