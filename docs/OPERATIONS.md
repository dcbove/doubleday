# Operations

Runbook for invoking Lambdas, running scripts, and managing data sources. For data model, see [DATALAKE.md](DATALAKE.md). For pipeline flow, see [PIPELINE.md](PIPELINE.md). For project overview, see [README.md](../README.md).

## Bronze Layer

### Downloading CSVs locally

```bash
bash scripts/download_year.sh <year>
```

One CSV per day across the MLB season (March through November). Baseball Savant caps exports at ~25,000 rows per request; the script warns if any file hits this limit.

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

## Silver Layer

### Invoking the silver_load Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-silver-load \
  --payload '{"season": 2024, "game_date": "2024-03-01", "batch_id": "manual-test"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

## Gold Layer

### Invoking the gold_load Lambda

```bash
# gold_pitches_shape_season
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_pitches_shape_season", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout

# gold_pitch_type_norm_stats (depends on gold_pitches_shape_season)
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_pitch_type_norm_stats", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout

# gold_repertoire_shape_neighbors (depends on gold_pitch_type_norm_stats)
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_repertoire_shape_neighbors", "season": 2024, "format_params": {"lambda": "0.4", "tau": "1"}}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout

# gold_catalog (depends on silver_pitches + silver_players + silver_teams)
aws lambda invoke \
  --function-name doubleday-dev-gold-load \
  --payload '{"table_name": "gold_catalog", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Reloading gold + DynamoDB for a season

To rebuild gold tables and DynamoDB serving tables without reprocessing bronze/silver:

```bash
bash scripts/gold_reload.sh 2024        # defaults to dev
bash scripts/gold_reload.sh 2024 prod   # specify environment
```

This runs the three gold loads in dependency order, then loads both DynamoDB entity types.

## Dimension Tables

### Invoking the dimension_load Lambda

```bash
# Load teams for a season
aws lambda invoke \
  --function-name doubleday-dev-dimension-load \
  --payload '{"dimension": "teams", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout

# Load games for specific dates
aws lambda invoke \
  --function-name doubleday-dev-dimension-load \
  --payload '{"dimension": "games", "season": 2024, "game_dates": ["2024-03-01", "2024-03-02"]}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

Valid dimensions: `teams`, `venues`, `games`, `umpires`, `players`. Use `force_download` to re-fetch from the MLB API (ignoring the bronze cache):

```bash
aws lambda invoke \
  --function-name doubleday-dev-dimension-load \
  --payload '{"dimension": "players", "season": 2024, "force_download": true}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

All five dimensions run automatically as a parallel step in the pipeline after silver load completes.

## DynamoDB Serving Layer

### Invoking the dynamodb_load Lambda

```bash
# Load pitches for a season
aws lambda invoke \
  --function-name doubleday-dev-dynamodb-load \
  --payload '{"entity_type": "pitches", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout

# Load neighbors for a season
aws lambda invoke \
  --function-name doubleday-dev-dynamodb-load \
  --payload '{"entity_type": "neighbors", "season": 2024}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

All three entity types run automatically as a parallel step in the pipeline after gold load completes.

## Pipeline Orchestration

### Invoking the Step Function

Runs the full pipeline for the given dates: bronze download, silver load, dimension load, gold rebuild, and DynamoDB load. Safe to re-run — bronze skips existing files, silver overwrites partitions idempotently, and dimension caches are reused.

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:<region>:<account>:stateMachine:doubleday-dev-pipeline \
  --input '{"season": 2024, "game_dates": ["2024-03-01"]}'
```

Multiple dates can be passed in a single execution. Use `force_download` to re-download files that already exist in S3:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:<region>:<account>:stateMachine:doubleday-dev-pipeline \
  --input '{"season": 2024, "game_dates": ["2024-03-01", "2024-03-02"], "force_download": true}'
```

### Backfilling a season

To process an entire season (March 1-Nov 30), use the backfill script:

```bash
bash scripts/backfill_season.sh 2024        # defaults to dev
bash scripts/backfill_season.sh 2024 prod   # specify environment
```

This generates all ~275 dates in the range and starts a single Step Function execution. Bronze load skips any dates already in S3 (unless `force_download` is set), so backfills are safe to re-run — only silver and gold do real work for previously downloaded data.

## Fast Lambda Code Deploy

To push code changes to Lambda without a full `terraform apply` (useful during development and integration test debugging):

```bash
# Single function
./scripts/deploy_lambda_code.sh doubleday-dev-dimension-load

# Multiple functions
./scripts/deploy_lambda_code.sh doubleday-dev-dimension-load doubleday-dev-gold-load

# All dev functions
./scripts/deploy_lambda_code.sh -a
```

The script builds the shared Lambda package, uploads it to S3 with a content hash, and fires `update-function-code` for all target functions in parallel. Much faster than Terraform, which waits for each function to stabilize sequentially.

## Diagnostics

### Table record counts

Print record counts per season for every bronze, silver, gold, and DynamoDB table. Useful for diagnosing incomplete backfills or verifying data after a pipeline run.

```bash
bash scripts/table_counts.sh          # defaults to dev
bash scripts/table_counts.sh prod     # specify environment
```

All Athena queries run in parallel for speed. DynamoDB counts use a full table scan per entity type, which may take a minute on large tables.

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

## Iceberg Table Recovery

If Iceberg table metadata is lost (e.g., S3 bucket contents deleted), Athena `DROP TABLE` will fail with `Iceberg cannot find the requested entity`. Delete the tables directly from the Glue catalog, then taint and reapply Terraform:

```bash
# Delete orphaned Glue catalog entries
aws glue delete-table --database-name doubleday_<env> --name silver_pitches_staging
aws glue delete-table --database-name doubleday_<env> --name silver_pitches
aws glue delete-table --database-name doubleday_<env> --name silver_teams
aws glue delete-table --database-name doubleday_<env> --name silver_venues
aws glue delete-table --database-name doubleday_<env> --name silver_games
aws glue delete-table --database-name doubleday_<env> --name silver_umpires
aws glue delete-table --database-name doubleday_<env> --name silver_players
aws glue delete-table --database-name doubleday_<env> --name gold_pitches_shape_season
aws glue delete-table --database-name doubleday_<env> --name gold_pitch_type_norm_stats
aws glue delete-table --database-name doubleday_<env> --name gold_repertoire_shape_neighbors
aws glue delete-table --database-name doubleday_<env> --name gold_catalog

# Taint Terraform resources so DDL provisioners re-run
cd terraform/environments/<env>
terraform taint 'module.doubleday.module.glue.null_resource.silver_pitches_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_pitches_staging_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_teams_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_venues_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_games_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_umpires_table'
terraform taint 'module.doubleday.module.glue.null_resource.silver_players_table'
terraform taint 'module.doubleday.module.glue.null_resource.gold_pitches_shape_season_table'
terraform taint 'module.doubleday.module.glue.null_resource.gold_pitch_type_norm_stats_table'
terraform taint 'module.doubleday.module.glue.null_resource.gold_repertoire_shape_neighbors_table'
terraform taint 'module.doubleday.module.glue.null_resource.gold_catalog_table'
terraform apply -target=module.doubleday.module.glue
```
