#!/usr/bin/env bash
set -euo pipefail

YEAR=${1:?Usage: backfill_season.sh <year>}
ENV=${2:-dev}

SEASON_START="${YEAR}-03-01"
SEASON_END="${YEAR}-11-30"

# Generate all dates in the range
dates=()
current=$(date -j -f "%Y-%m-%d" "$SEASON_START" +%s)
end=$(date -j -f "%Y-%m-%d" "$SEASON_END" +%s)
day=86400

while [ "$current" -le "$end" ]; do
  dates+=("\"$(date -j -f "%s" "$current" +%Y-%m-%d)\"")
  current=$((current + day))
done

game_dates=$(IFS=,; echo "${dates[*]}")
input="{\"season\": ${YEAR}, \"game_dates\": [${game_dates}]}"

echo "Starting backfill for ${YEAR} (${#dates[@]} dates) on doubleday-${ENV}-pipeline"

arn="arn:aws:states:us-east-1:$(aws sts get-caller-identity --query Account --output text):stateMachine:doubleday-${ENV}-pipeline"

aws stepfunctions start-execution \
  --state-machine-arn "$arn" \
  --input "$input"
