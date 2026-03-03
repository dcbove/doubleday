#!/usr/bin/env bash
# Backfill all dimension tables for a given season.
# Assumes silver_pitches and silver_games are already loaded.
#
# Games requires all dates in the season. Teams, venues, umpires, and
# players are season-scoped and need a single invocation each.
#
# Usage: backfill_dimensions.sh <year> [environment]
set -euo pipefail

YEAR=${1:?Usage: backfill_dimensions.sh <year> [environment]}
ENV=${2:-dev}
PREFIX="doubleday-${ENV}"
FUNC="${PREFIX}-dimension-load"

SEASON_START="${YEAR}-03-01"
SEASON_END="${YEAR}-11-30"

invoke() {
  local payload=$1
  echo "  Invoking ${FUNC} ..."
  aws lambda invoke \
    --function-name "$FUNC" \
    --payload "$payload" \
    --cli-binary-format raw-in-base64-out \
    --cli-read-timeout 900 \
    /dev/stdout
  echo
}

echo "=== Dimension backfill for season ${YEAR} on ${PREFIX} ==="

echo "Step 1/5: teams"
invoke "{\"dimension\": \"teams\", \"season\": ${YEAR}}"

echo "Step 2/5: venues"
invoke "{\"dimension\": \"venues\", \"season\": ${YEAR}}"

echo "Step 3/5: games (generating dates ${SEASON_START} to ${SEASON_END})"
dates=()
current="$SEASON_START"
while [[ "$current" < "$SEASON_END" || "$current" == "$SEASON_END" ]]; do
  dates+=("\"${current}\"")
  current=$(date -j -v+1d -f "%Y-%m-%d" "$current" +%Y-%m-%d)
done

game_dates=$(IFS=,; echo "${dates[*]}")
invoke "{\"dimension\": \"games\", \"season\": ${YEAR}, \"game_dates\": [${game_dates}]}"

echo "Step 4/5: umpires"
invoke "{\"dimension\": \"umpires\", \"season\": ${YEAR}}"

echo "Step 5/5: players"
invoke "{\"dimension\": \"players\", \"season\": ${YEAR}}"

echo "=== Done ==="
