# Operations

Runbook for invoking Lambdas, running scripts, and managing data sources. For project architecture and development setup, see [README.md](../README.md).

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
```

### Reloading gold + DynamoDB for a season

To rebuild gold tables and DynamoDB serving tables without reprocessing bronze/silver:

```bash
bash scripts/gold_reload.sh 2024        # defaults to dev
bash scripts/gold_reload.sh 2024 prod   # specify environment
```

This runs the three gold loads in dependency order, then loads both DynamoDB entity types.

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

Both entity types run automatically as a parallel step in the pipeline after gold load completes.

## Player Catalogs

### Invoking the catalog_build Lambda

```bash
aws lambda invoke \
  --function-name doubleday-dev-catalog-build \
  --cli-binary-format raw-in-base64-out \
  --payload '{"season": 2024, "role": "pitchers"}' \
  /dev/stdout
```

Use `force_rebuild` to re-fetch all enrichment data from the MLB API (ignoring the cache):

```bash
aws lambda invoke \
  --function-name doubleday-dev-catalog-build \
  --cli-binary-format raw-in-base64-out \
  --payload '{"season": 2024, "role": "pitchers", "force_rebuild": true}' \
  /dev/stdout
```

### Rebuilding catalogs for a season

```bash
bash scripts/catalog_rebuild.sh 2024        # defaults to dev
bash scripts/catalog_rebuild.sh 2024 prod   # specify environment
```

This rebuilds both pitchers and batters catalogs for the given season.

## Pipeline Orchestration

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

To process an entire season (March 1-Nov 30), use the backfill script:

```bash
bash scripts/backfill_season.sh 2024        # defaults to dev
bash scripts/backfill_season.sh 2024 prod   # specify environment
```

This generates all ~275 dates in the range and starts a single Step Function execution. Bronze load skips any dates already in S3 (unless `force_download` is set), so backfills are safe to re-run — only silver and gold do real work for previously downloaded data.

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
aws glue delete-table --database-name doubleday_<env> --name gold_pitches_shape_season
aws glue delete-table --database-name doubleday_<env> --name gold_pitch_type_norm_stats
aws glue delete-table --database-name doubleday_<env> --name gold_repertoire_shape_neighbors

# Taint Terraform resources so DDL provisioners re-run
cd terraform/environments/<env>
terraform taint 'module.doubleday.module.glue.null_resource.silver_pitches_ddl'
terraform taint 'module.doubleday.module.glue.null_resource.silver_pitches_staging_ddl'
terraform taint 'module.doubleday.module.glue.null_resource.gold_pitches_shape_season_ddl'
terraform taint 'module.doubleday.module.glue.null_resource.gold_pitch_type_norm_stats_ddl'
terraform taint 'module.doubleday.module.glue.null_resource.gold_repertoire_shape_neighbors_ddl'
terraform apply -target=module.doubleday.module.glue
```
