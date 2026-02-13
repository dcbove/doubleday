# Doubleday ETL Pipeline Roadmap

End-to-end Statcast ETL pipeline orchestrated by a Step Function.

## Architecture

```
Step Function (Standard)
  Input: {"season": 2025, "game_dates": ["2025-05-14"]}

  → Map over game_dates (concurrency-limited):
      → bronze_load(game_date)     # download from Baseball Savant → S3
      → silver_load(game_date)     # bronze → silver partition overwrite
  → For each gold table:
      → gold_load(season, table)   # silver → gold partition overwrite (once)
```

Three Lambdas, one Standard Step Function. All serverless, no idle cost.

## Design Decisions

### Partition overwrite (not MERGE) for gold tables

Same rationale as silver (see README). Gold tables are full-season aggregations rebuilt from silver. Overwriting the season partition is simpler, deterministic, and avoids row-level merge complexity. If any upstream data changed, the overwrite produces the correct result without reasoning about deltas.

### Standard over Express Step Functions

Standard Step Functions support executions up to one year and have detailed execution history. This matters for backfills — reprocessing an entire season (180+ game dates) can take well over five minutes, which is the Express maximum. Standard also provides per-step visibility in the console, making debugging straightforward.

### Single parameterized gold Lambda

One `gold_load` Lambda accepts a table name parameter and executes the corresponding SQL. Adding a new gold table means adding a SQL file and a Step Function entry — no Lambda code changes. This keeps the gold layer extensible without deployment churn.

### Step Function as single entry point

All processing flows through the Step Function. There are no S3 event triggers or independent Lambda invocations in production. This eliminates double-processing, makes the pipeline easy to reason about, and gives a single place to monitor execution status.

## Phases

### Phase 1 — Gold Load Lambda + Step Function (silver → gold)

Bronze and silver infrastructure already exist. This phase adds the gold layer and the Step Function that ties everything together.

#### Deliverables

1. **Gold table DDL** — Iceberg CREATE TABLE for `gold_pitches_shape_season`, partitioned by `season`. SQL in `sql/ddl/gold_pitches_shape_season.sql`.
2. **Gold load SQL** — INSERT OVERWRITE query that reads from `silver_pitches` and writes aggregated results into the gold table. Parameterized by season. SQL in `sql/pipeline/gold_pitches_shape_season.sql` (derived from the existing draft query).
3. **`gold_load` Lambda** — Python handler + pipeline, parameterized by table name. Reads the corresponding `_load.sql` file, substitutes parameters (`season`, database name), executes via Athena. Lives in `src/doubleday/lambdas/gold_load/`.
4. **Terraform module for `gold_load`** — Lambda function, IAM role, zip packaging. Mirrors the existing `lambda` module pattern.
5. **Update Glue module** — Add gold table DDL to Glue `null_resource` provisioners so `terraform apply` creates the table.
6. **Standard Step Function** — Orchestrates `silver_load` → `gold_load` (per gold table). Input: `{"season": 2025, "game_dates": ["2025-05-14"]}`. Map state iterates over `game_dates` calling `silver_load`, then parallel/map state calls `gold_load` for each gold table.
7. **Terraform module for Step Function** — State machine definition, IAM role with Lambda invoke permissions, CloudWatch logging.
8. **Unit tests** — Tests for gold pipeline logic (SQL parameterization, handler event parsing, error handling).
9. **Wire into dev environment** — Add gold and step function modules to `terraform/environments/dev/`.

#### Sequence

```
DDL + load SQL → gold_load Lambda → Terraform (Lambda + Glue) → Step Function → Terraform (Step Function) → tests → dev wiring
```

### Phase 2 — Bronze Load Lambda

Replace the manual `download_year.sh` + `aws s3 sync` workflow with a Lambda that downloads directly from Baseball Savant into S3.

#### Deliverables

1. **`bronze_load` Lambda** — Downloads Statcast CSV for a single game date from Baseball Savant, writes to `s3://doubleday-<env>-lakehouse/bronze/season=<year>/game_date=<date>/statcast.csv`. Lives in `src/doubleday/lambdas/bronze_load/`.
2. **Terraform module for `bronze_load`** — Lambda function, IAM role, zip packaging.
3. **Update Step Function** — Add `bronze_load` as the first step in the per-game-date Map iteration: `bronze_load → silver_load`.
4. **Unit tests** — Tests for bronze download logic.
5. **Retire manual workflow** — `download_year.sh` remains available but is no longer the primary ingestion path.

### Phase 3 — Scheduled Automation

Trigger the pipeline automatically so daily games are processed without manual intervention.

#### Deliverables

1. **EventBridge scheduled rule** — Triggers the Step Function on a daily schedule (e.g., 10:00 UTC, after overnight game finalization).
2. **Date resolution** — Determine how the schedule resolves "which game dates to process." Options: pass yesterday's date, query an MLB schedule API, or use a fixed offset.
3. **Terraform for EventBridge** — Rule, target, IAM permissions.
4. **Monitoring** — CloudWatch alarms for Step Function failures.

## Current State

| Component | Status |
|-----------|--------|
| Bronze download script | Done (`util/download_year.sh`) |
| Bronze S3 + Glue table | Done (Terraform) |
| Silver load Lambda | Done (`src/doubleday/lambdas/silver_load/`) |
| Silver Terraform (Lambda + Glue) | Done |
| Gold DDL | Done (`sql/ddl/gold_pitches_shape_season.sql`) |
| Gold load SQL | Done (`sql/pipeline/gold_pitches_shape_season.sql`) |
| Gold load Lambda | Done (`src/doubleday/lambdas/gold_load/`) |
| Gold load Terraform | Done (`terraform/modules/gold_load/`) |
| Step Function | Done (`terraform/modules/step_function/`) |
| Validate input Lambda | Done (`src/doubleday/lambdas/validate_input/`) |
| Bronze load Lambda | Done (`src/doubleday/lambdas/bronze_load/`) |
| Scheduled automation | Not started |
