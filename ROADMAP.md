# Doubleday ETL Pipeline Roadmap



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
| Bronze download script | Done (`scripts/download_year.sh`) |
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
