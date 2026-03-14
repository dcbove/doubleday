#!/usr/bin/env bash
# Fast Lambda code deploy — bypasses Terraform to push code in seconds.
#
# Builds per-Lambda zips with Bazel, uploads each to S3 with a content hash,
# then updates the Lambda function to point at the new artifact.
#
# Why this is faster than Terraform:
# Terraform waits for each Lambda update to stabilize (Pending → Active),
# which takes ~10-30s per function and runs mostly in series due to AWS
# API throttling. This script fires update-function-code calls without
# waiting for stabilization, so all functions update in parallel.
#
# Usage:
#   ./scripts/deploy_lambda_code.sh <function-name> [function-name...]
#   ./scripts/deploy_lambda_code.sh -f functions.txt
#   ./scripts/deploy_lambda_code.sh -a              # all dev functions
set -euo pipefail

S3_BUCKET="cf-templates-1hp7zsrryx93f-us-east-1"
S3_PREFIX="doubleday/lambda-artifacts"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# All dev Lambda function names (doubleday-dev-*)
ALL_FUNCTIONS=(
  doubleday-dev-bronze-load
  doubleday-dev-silver-load
  doubleday-dev-clear-staging
  doubleday-dev-validate-input
  doubleday-dev-check-failures
  doubleday-dev-gold-load
  doubleday-dev-dynamodb-load
  doubleday-dev-dimension-load
  doubleday-dev-daily-trigger
  doubleday-dev-api-authorizer
  doubleday-dev-api-catalog
  doubleday-dev-api-query-pitches
  doubleday-dev-api-query-neighbors
  doubleday-dev-api-create-checkout
  doubleday-dev-api-customer-portal
  doubleday-dev-api-subscription-status
  doubleday-dev-api-stripe-events
)

# Map function names to per-Lambda zip names in builds/lambdas/.
function_to_zip() {
  local fn="$1"
  # Strip "doubleday-dev-" or "doubleday-prod-" prefix, then "api-" if present.
  local name="${fn#doubleday-*-}"
  name="${name#api-}"
  # Convert hyphens to underscores to match zip names.
  echo "${name//-/_}"
}

# ── Prerequisite checks ──────────────────────────────────────────────

for cmd in aws bazel shasum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: '$cmd' not found"; exit 1; }
done

# ── Parse arguments ───────────────────────────────────────────────────

functions=()

if [[ $# -eq 0 ]]; then
  echo "Usage:"
  echo "  $0 <function-name> [function-name...]"
  echo "  $0 -f functions.txt"
  echo "  $0 -a                  # all dev functions"
  exit 1
fi

if [[ "$1" == "-a" ]]; then
  functions=("${ALL_FUNCTIONS[@]}")
elif [[ "$1" == "-f" ]]; then
  [[ -z "${2:-}" ]] && { echo "ERROR: -f requires a filename"; exit 1; }
  while IFS= read -r line; do
    [[ -n "$line" && "$line" != \#* ]] && functions+=("$line")
  done < "$2"
else
  functions=("$@")
fi

[[ ${#functions[@]} -eq 0 ]] && { echo "ERROR: no functions specified"; exit 1; }

# ── Build packages ───────────────────────────────────────────────────

echo "Building Lambda packages with Bazel..."
cd "$PROJECT_ROOT"
bazel build //src/doubleday/...
bash "$SCRIPT_DIR/copy_lambda_zips.sh"

# ── Upload and update each function ─────────────────────────────────

echo ""
echo "Updating ${#functions[@]} function(s)..."

pids=()
for fn in "${functions[@]}"; do
  zip_name="$(function_to_zip "$fn")"
  ZIP_PATH="$PROJECT_ROOT/builds/lambdas/${zip_name}.zip"

  if [[ ! -f "$ZIP_PATH" ]]; then
    echo "  WARNING: no zip for $fn (expected $ZIP_PATH), skipping"
    continue
  fi

  HASH=$(shasum -a 256 "$ZIP_PATH" | cut -c1-12)
  S3_KEY="${S3_PREFIX}/${zip_name}-${HASH}.zip"

  echo "  → $fn ($(du -h "$ZIP_PATH" | cut -f1) → s3://${S3_BUCKET}/${S3_KEY})"

  (
    aws s3 cp "$ZIP_PATH" "s3://${S3_BUCKET}/${S3_KEY}" --quiet
    aws lambda update-function-code \
      --function-name "$fn" \
      --s3-bucket "$S3_BUCKET" \
      --s3-key "$S3_KEY" \
      --output text --query 'FunctionName' > /dev/null
  ) &
  pids+=($!)
done

# Wait for all updates to complete.
failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=$((failed + 1))
  fi
done

echo ""
if [[ $failed -gt 0 ]]; then
  echo "WARNING: $failed function update(s) failed."
  exit 1
else
  echo "Done. All ${#functions[@]} function(s) updated."
fi
