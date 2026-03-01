#!/usr/bin/env bash
# Reload gold tables and DynamoDB serving tables for a given season.
# Skips bronze and silver — assumes silver data is already loaded.
#
# Usage: gold_reload.sh <year> [environment]
set -euo pipefail

YEAR=${1:?Usage: gold_reload.sh <year> [environment]}
ENV=${2:-dev}
PREFIX="doubleday-${ENV}"

invoke() {
  local func=$1
  local payload=$2
  echo "  Invoking ${func} ..."
  aws lambda invoke \
    --function-name "$func" \
    --payload "$payload" \
    --cli-binary-format raw-in-base64-out \
    /dev/stdout
  echo
}

echo "=== Gold reload for season ${YEAR} on ${PREFIX} ==="

echo "Step 1/5: gold_pitches_shape_season"
invoke "${PREFIX}-gold-load" \
  "{\"table_name\": \"gold_pitches_shape_season\", \"season\": ${YEAR}}"

echo "Step 2/5: gold_pitch_type_norm_stats"
invoke "${PREFIX}-gold-load" \
  "{\"table_name\": \"gold_pitch_type_norm_stats\", \"season\": ${YEAR}}"

echo "Step 3/5: gold_repertoire_shape_neighbors"
invoke "${PREFIX}-gold-load" \
  "{\"table_name\": \"gold_repertoire_shape_neighbors\", \"season\": ${YEAR}, \"format_params\": {\"lambda\": \"0.4\", \"tau\": \"1\"}}"

echo "Step 4/5: dynamodb_load pitches"
invoke "${PREFIX}-dynamodb-load" \
  "{\"entity_type\": \"pitches\", \"season\": ${YEAR}}"

echo "Step 5/5: dynamodb_load neighbors"
invoke "${PREFIX}-dynamodb-load" \
  "{\"entity_type\": \"neighbors\", \"season\": ${YEAR}}"

echo "=== Done ==="
