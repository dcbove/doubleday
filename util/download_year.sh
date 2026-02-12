#!/usr/bin/env bash
set -euo pipefail

YEAR=${1:?Usage: download_year.sh <year>}
OUTDIR="data/bronze/statcast_${YEAR}"
mkdir -p "$OUTDIR"

SEASON_START="${YEAR}-03-01"
SEASON_END="${YEAR}-12-01"

current=$(date -j -f "%Y-%m-%d" "$SEASON_START" +%s)
end=$(date -j -f "%Y-%m-%d" "$SEASON_END" +%s)
day=86400

while [ "$current" -lt "$end" ]; do
  day_date=$(date -j -f "%s" "$current" +%Y-%m-%d)

  out="${OUTDIR}/statcast_${day_date}.csv"
  echo "Downloading $day_date to $out"

  curl -L \
    "https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt=${day_date}&game_date_lt=${day_date}" \
    -o "$out"

  lines=$(wc -l < "$out")
  if [ "$lines" -ge 25001 ]; then
    echo "WARNING: $out has $lines lines (likely hit cap)."
  fi

  sleep 2
  current=$((current + day))
done
