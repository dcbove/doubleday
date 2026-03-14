#!/usr/bin/env bash
# Copy Bazel-built Lambda zips to builds/lambdas/ for Terraform.
# Run after: bazel build //src/doubleday/...
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

rm -rf builds/lambdas
mkdir -p builds/lambdas

# Pipeline Lambdas
for name in validate_input check_failures bronze_load silver_load clear_staging \
            gold_load dynamodb_load dimension_load daily_trigger; do
  cp "bazel-bin/src/doubleday/pipeline/${name}/${name}.zip" "builds/lambdas/${name}.zip"
done

# API Lambdas
for name in authorizer catalog query_pitches query_neighbors \
            create_checkout customer_portal stripe_events subscription_status; do
  cp "bazel-bin/src/doubleday/api/${name}/${name}.zip" "builds/lambdas/${name}.zip"
done

echo "Copied $(ls builds/lambdas/*.zip | wc -l | tr -d ' ') Lambda zips to builds/lambdas/"
