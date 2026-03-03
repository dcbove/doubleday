#!/usr/bin/env bash
set -euo pipefail

YEAR=${1:?Usage: download_year.sh <year>}
OUTDIR="data/bronze"
mkdir -p "$OUTDIR"

SEASON_START="${YEAR}-08-13"
SEASON_END="${YEAR}-12-01"

current="$SEASON_START"

while [[ "$current" < "$SEASON_END" ]]; do
  day_date="$current"

  day_dir="${OUTDIR}/season=${YEAR}/game_date=${day_date}"
  mkdir -p "$day_dir"
  out="${day_dir}/statcast.csv"
  echo "Downloading $day_date to $out"

  curl -L \
    "https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt=${day_date}&game_date_lt=${day_date}" \
    -o "$out"

  lines=$(wc -l < "$out")
  if [ "$lines" -ge 25001 ]; then
    echo "WARNING: $out has $lines lines (likely hit cap)."
  fi

  sleep 2
  current=$(date -j -v+1d -f "%Y-%m-%d" "$current" +%Y-%m-%d)
done
