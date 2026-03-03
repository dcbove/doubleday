#!/usr/bin/env bash
set -euo pipefail

YEAR=${1:?Usage: backfill_season.sh <year>}
ENV=${2:-dev}

SEASON_START="${YEAR}-03-01"
SEASON_END="${YEAR}-11-30"

# Generate all dates in the range
dates=()
current="$SEASON_START"
while [[ "$current" < "$SEASON_END" || "$current" == "$SEASON_END" ]]; do
  dates+=("\"${current}\"")
  current=$(date -j -v+1d -f "%Y-%m-%d" "$current" +%Y-%m-%d)
done

game_dates=$(IFS=,; echo "${dates[*]}")
input="{\"season\": ${YEAR}, \"game_dates\": [${game_dates}]}"

echo "Starting backfill for ${YEAR} (${#dates[@]} dates) on doubleday-${ENV}-pipeline"

arn="arn:aws:states:us-east-1:$(aws sts get-caller-identity --query Account --output text):stateMachine:doubleday-${ENV}-pipeline"

execution_name="backfill-${YEAR}-$(date +%Y%m%dT%H%M%S)-$(uuidgen | head -c 8)"

aws stepfunctions start-execution \
  --state-machine-arn "$arn" \
  --name "$execution_name" \
  --input "$input"
