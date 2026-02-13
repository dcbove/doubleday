# Doubleday

Analysis and processing of pitch-by-pitch MLB data sourced from Baseball Savant's Statcast system.

## Setup

```bash
brew install pyenv uv
pyenv install 3.13

git clone <repo-url> doubleday
cd doubleday
make install
```

`make install` installs dependencies and configures the pre-commit hook (see [Pre-commit hooks](#pre-commit-hooks)).

## Project structure

```
src/doubleday/
  lambdas/
    silver_load/
      handler.py        # Lambda entry point — event parsing, metrics, response
      pipeline.py       # Business logic — stage, validate, merge pipeline
    gold_load/
      handler.py        # Lambda entry point — event parsing, metrics, response
      pipeline.py       # Business logic — partition overwrite pipeline
  util/
    athena.py           # Shared Athena query execution utilities
  main.py              # CLI entry point
sql/
  ddl/
    silver_pitches.sql                              # Iceberg DDL (canonical)
    silver_pitches_staging.sql                      # Iceberg DDL (staging)
    gold_pitches_shape_season.sql                   # Iceberg DDL (pitch shape aggs)
  pipeline/
    silver_clear_partition_from_staging_table.sql    # Delete partition from staging
    silver_load_partition_into_staging_table.sql     # Bronze -> staging INSERT
    silver_validate_staging_table.sql               # Duplicate key check on staging
    silver_merge_partition_into_canonical_table.sql  # Staging -> canonical MERGE
    gold_pitches_shape_season.sql                   # Delete + INSERT from silver
terraform/
  environments/dev/     # Dev environment root (plan/apply from here)
  modules/
    s3/                 # Lakehouse bucket
    glue/               # Database and table DDL (bronze, silver, gold)
    lambda/             # Lambda functions (silver_load, gold_load), IAM, packaging
    step_function/      # Pipeline Step Function, IAM, logging
tests/
  test_main.py                              # Unit tests
  test_gold_load_pipeline.py                # Gold load unit tests
  integration/
    test_silver_pitches_load.py             # Silver load integration tests
util/
  download_year.sh      # Download Statcast CSVs from Baseball Savant
```

Handler code (`handler.py`) is separated from business logic (`pipeline.py`) so the pipeline can be tested and reused without a Lambda runtime. Shared utilities like Athena query execution live in `src/doubleday/util/` for use across Lambdas and tests.

## Development

```bash
make test               # Run unit tests (excludes integration)
make test-integration   # Run integration tests (requires AWS credentials)
make lint               # Lint with ruff
make format             # Format with black
make typecheck          # Type check with mypy
make check-all          # Run all checks (lint, format, typecheck, unit tests)
```

### Pre-commit hooks

A pre-commit hook runs `make check-all` before every commit. It is installed automatically by `make install`, or manually:

```bash
make install-hooks
```

This sets `core.hooksPath` to `.githooks/`, which is tracked in the repo — no extra tooling needed.

### Code standards

- All Python modules, public functions, classes, and methods must have docstrings (Google-style convention).
- Enforced by Ruff (`D` rules) — `ruff check` will fail on missing docstrings.
- Formatting: black. Type checking: mypy. Linting: ruff.
- See `CLAUDE.md` for AI-assisted development guidelines.

## Data: Bronze Layer

The bronze layer is raw, unmodified Statcast pitch-by-pitch CSV data downloaded from Baseball Savant. All columns are stored as strings. Data is Hive-style partitioned by season and game date for use with Athena and Glue.

### Download

```bash
bash util/download_year.sh <year>
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

The silver layer is the canonical, typed source of truth. Data is stored as Apache Iceberg tables in Parquet format, partitioned by `(season, game_date)`. Deprecated columns from the bronze layer are dropped and all remaining columns are strongly typed.

### Tables

- **`silver_pitches`** — canonical pitch-by-pitch table. Supports idempotent loads via MERGE on `(game_pk, at_bat_number, pitch_number)`.
- **`silver_pitches_staging`** — transient scratch table with the same schema. Used to stage one day's data at a time before merging into canonical.

### Table creation

Tables are created via Athena DDL, triggered automatically by `terraform apply` through `null_resource` provisioners. The SQL definitions live in:

```
sql/ddl/silver_pitches.sql
sql/ddl/silver_pitches_staging.sql
```

Schema evolution (adding columns, changing types) should be done via Athena `ALTER TABLE` statements, not by modifying the Glue catalog directly — Iceberg manages its own metadata in S3.

### Silver load pipeline

The `silver-load` Lambda loads a single `(season, game_date)` partition from bronze to silver. The pipeline runs these steps in order:

1. **Clear staging** — delete the partition from `silver_pitches_staging`
2. **Load partition** — INSERT from `bronze_statcast` into `silver_pitches_staging` with type casting
3. **Validate staging** — check for duplicate `(game_pk, at_bat_number, pitch_number)` keys; fail before merge if any found
4. **Merge partition** — MERGE from staging into `silver_pitches` (insert new rows, update existing)
5. **Clear staging** — clean up the staging table

If validation fails, the canonical table is untouched.

### Why partition overwrite (not MERGE)

In Iceberg, partition overwrite and merge upserts represent two different update models. A partition overwrite rewrites all data within a logical partition (e.g., `season=2025/game_date=2025-05-14`) as a single atomic operation. Iceberg creates a new snapshot that replaces the files for that partition, without needing to reason about individual row changes. A MERGE upsert, by contrast, operates at row granularity: it matches existing rows on a key, updates those that match, inserts those that don't, and may produce both new data files and delete files under the hood. Merge is more flexible but introduces additional metadata churn, potential small-file fragmentation, and greater operational complexity.

We chose partition overwrite because Statcast game data is effectively immutable once finalized. Our ingestion unit is already aligned to a natural partition boundary `(season, game_date)`, and reprocessing a day means "replace that day," not "surgically edit individual pitches." Overwrite keeps the pipeline deterministic, simplifies correctness reasoning (no row-level keys or match logic required), and minimizes operational surface area. For our workload, merge would add complexity without providing meaningful benefit.

### Invoking the Lambda

The Lambda expects a `partition_name` in the event payload:

```bash
aws lambda invoke \
  --function-name doubleday-dev-silver-load \
  --payload '{"partition_name": "season=2024/game_date=2024-03-01"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Iceberg introspection

View snapshot history (each load/merge creates a new snapshot):

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

### S3 layout

```
s3://doubleday-<env>-lakehouse/silver/
├── silver_pitches/            # Iceberg data + metadata
└── silver_pitches_staging/    # Iceberg data + metadata
```

## Data: Gold Layer

The gold layer contains precomputed analytical tables built from silver. Each table is an Iceberg table partitioned by `season` and loaded via partition overwrite (DELETE + INSERT). Gold tables are rebuilt from scratch whenever the pipeline runs — there is no incremental merge.

### Tables

- **`gold_pitches_shape_season`** — per-pitcher, per-pitch-type season aggregations including movement, velocity, spin, and usage metrics. Minimum 50-pitch threshold per pitch type.

### Table creation

Tables are created via Athena DDL, triggered by `terraform apply`:

```
sql/ddl/gold_pitches_shape_season.sql
```

### Gold load pipeline

The `gold-load` Lambda loads a single gold table for a given season. It reads a SQL file containing both a DELETE (clear the season partition) and an INSERT (rebuild from silver), splits them into statements, and executes each in order.

### Invoking the Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_pitches_shape_season", "season": 2025}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### S3 layout

```
s3://doubleday-<env>-lakehouse/gold/
└── gold_pitches_shape_season/    # Iceberg data + metadata
```

## Pipeline Orchestration

A Standard Step Function orchestrates the full ETL pipeline. Input:

```json
{"season": 2025, "game_dates": ["2025-05-14"], "gold_tables": ["gold_pitches_shape_season"]}
```

The pipeline:

1. **Map over game_dates** (concurrency 5) — invoke `silver_load` for each date
2. **Map over gold_tables** — invoke `gold_load` for each table with the season

### Invoking the Step Function

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:<region>:<account>:stateMachine:doubleday-dev-pipeline \
  --input '{"season": 2025, "game_dates": ["2025-05-14"], "gold_tables": ["gold_pitches_shape_season"]}'
```

## Testing

### Unit tests

```bash
make test
```

### Integration tests

Integration tests invoke the real Lambda against live Athena/Iceberg tables in the dev environment. They require valid AWS credentials.

```bash
make test-integration
```

Each test clears the test partition (`season=2024/game_date=2024-03-01`) from both staging and canonical before running, so they are safe to re-run.

## Infrastructure

Infrastructure is managed with Terraform. The dev environment is the deployment root:

```bash
cd terraform/environments/dev
terraform init
terraform plan
terraform apply
```

### Modules

| Module | Description |
|--------|-------------|
| `s3` | Lakehouse S3 bucket |
| `glue` | Glue database, bronze/silver/gold table DDL |
| `lambda` | Lambda functions (silver_load, gold_load), IAM roles, zip packaging |
| `step_function` | Pipeline Step Function, IAM role, CloudWatch logging |

All Lambda functions share a single deployment zip built by Terraform's `archive_file` data source. It bundles the full `doubleday` Python package from `src/` along with all SQL templates from `sql/pipeline/`. Each Lambda points at the same zip with a different handler entry point. Changing any Python or SQL file triggers a redeployment of all functions, keeping them in sync.
