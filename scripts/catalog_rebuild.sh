#!/usr/bin/env bash
# Rebuild player catalogs for a given season.
#
# Usage: catalog_rebuild.sh <year> [environment]
set -euo pipefail

YEAR=${1:?Usage: catalog_rebuild.sh <year> [environment]}
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

echo "=== Catalog rebuild for season ${YEAR} on ${PREFIX} ==="

echo "Step 1/2: pitchers"
invoke "${PREFIX}-catalog-build" \
  "{\"season\": ${YEAR}, \"role\": \"pitchers\"}"

echo "Step 2/2: batters"
invoke "${PREFIX}-catalog-build" \
  "{\"season\": ${YEAR}, \"role\": \"batters\"}"

echo "=== Done ==="
