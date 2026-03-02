#!/usr/bin/env bash
# Print record counts per season for every bronze, silver, gold, and DynamoDB table.
# Useful for diagnosing incomplete backfills or missing data.
#
# Usage: table_counts.sh [environment]
set -euo pipefail

ENV=${1:-dev}
DATABASE="doubleday_${ENV}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
OUTPUT_BUCKET="doubleday-${ENV}-athena-results-${ACCOUNT}"
SERVING_TABLE="doubleday-${ENV}-serving"

# Temp dir for result files
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ── Athena helpers ────────────────────────────────────────────────────────────

start_count_query() {
  local table=$1
  local partition_col=$2
  local sql="SELECT ${partition_col}, COUNT(*) AS cnt FROM ${table} GROUP BY ${partition_col} ORDER BY ${partition_col}"
  aws athena start-query-execution \
    --query-string "$sql" \
    --query-execution-context "Database=${DATABASE}" \
    --result-configuration "OutputLocation=s3://${OUTPUT_BUCKET}/" \
    --output text --query 'QueryExecutionId'
}

# Wait for query and write "season count" lines to a file
wait_and_save() {
  local exec_id=$1
  local outfile=$2

  if [ "$exec_id" = "FAILED" ]; then
    echo "SUBMIT_FAILED" > "$outfile"
    return 0
  fi

  while true; do
    local status
    status=$(aws athena get-query-execution \
      --query-execution-id "$exec_id" \
      --output text --query 'QueryExecution.Status.State')
    case "$status" in
      SUCCEEDED) break ;;
      FAILED|CANCELLED)
        echo "QUERY_FAILED" > "$outfile"
        return 0
        ;;
      *) sleep 2 ;;
    esac
  done

  aws athena get-query-results \
    --query-execution-id "$exec_id" \
    --output json \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
rows = data['ResultSet']['Rows'][1:]
for row in rows:
    cols = [c.get('VarCharValue', '') for c in row['Data']]
    print(f'{cols[0]} {cols[1]}')
" > "$outfile"
}

# ── DynamoDB helper ───────────────────────────────────────────────────────────

dynamo_count() {
  local entity_type=$1
  local outfile=$2
  uv run python3 -c "
import boto3
from collections import Counter

table = boto3.resource('dynamodb').Table('${SERVING_TABLE}')
counts = Counter()
kwargs = {
    'Select': 'SPECIFIC_ATTRIBUTES',
    'ProjectionExpression': 'PK',
    'FilterExpression': 'entity_type = :et',
    'ExpressionAttributeValues': {':et': '${entity_type}'},
}
while True:
    resp = table.scan(**kwargs)
    for item in resp['Items']:
        pk = item['PK']
        parts = pk.split('#')
        try:
            season_idx = parts.index('SEASON')
            season = parts[season_idx + 1]
        except (ValueError, IndexError):
            season = 'unknown'
        counts[season] += 1
    if 'LastEvaluatedKey' not in resp:
        break
    kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

for season in sorted(counts):
    print(f'{season} {counts[season]}')
" > "$outfile"
}

# ── Table printer ─────────────────────────────────────────────────────────────

print_table() {
  local header=$1
  shift
  # Remaining args are "label:file" pairs
  # Collect all seasons across all files, then print a table

  python3 -c "
import sys
from collections import OrderedDict

header = '${header}'
pairs = sys.argv[1:]

# Parse label:file pairs
tables = OrderedDict()
all_seasons = set()
for pair in pairs:
    label, path = pair.split(':', 1)
    counts = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line in ('SUBMIT_FAILED', 'QUERY_FAILED'):
                    counts = {'ERROR': line}
                    break
                parts = line.split()
                if len(parts) == 2:
                    counts[parts[0]] = parts[1]
    except FileNotFoundError:
        counts = {'ERROR': 'NO_DATA'}
    tables[label] = counts
    all_seasons.update(k for k in counts if k != 'ERROR')

seasons = sorted(all_seasons)
if not seasons:
    print(f'{header}')
    print('  (no data)')
    print()
    sys.exit(0)

# Column widths
label_width = max(len(l) for l in tables)
col_widths = {}
for s in seasons:
    w = len(s)
    for counts in tables.values():
        w = max(w, len(counts.get(s, '-')))
    col_widths[s] = w

# Header
print(header)
row = f\"{'Table':<{label_width}}\"
for s in seasons:
    row += f'  {s:>{col_widths[s]}}'
print(f'  {row}')
print(f\"  {'-' * len(row)}\")

# Rows
for label, counts in tables.items():
    if 'ERROR' in counts:
        row = f'{label:<{label_width}}  {counts[\"ERROR\"]}'
    else:
        row = f'{label:<{label_width}}'
        for s in seasons:
            val = counts.get(s, '-')
            row += f'  {val:>{col_widths[s]}}'
    print(f'  {row}')
print()
" "$@"
}

# ── Main ──────────────────────────────────────────────────────────────────────

echo "=== Table counts for doubleday-${ENV} ==="
echo

# Submit all Athena queries in parallel
TABLES=(
  "bronze_statcast:season"
  "silver_pitches:season"
  "silver_pitches_staging:season"
  "silver_teams:season"
  "silver_venues:season"
  "silver_games:season"
  "silver_umpires:season"
  "silver_players:season"
  "gold_pitches_shape_season:season"
  "gold_pitch_type_norm_stats:pitch_type"
  "gold_repertoire_shape_neighbors:source_season"
  "gold_catalog:season"
)

EXEC_IDS=()
echo "Submitting ${#TABLES[@]} Athena queries..."
for entry in "${TABLES[@]}"; do
  table="${entry%%:*}"
  partition="${entry##*:}"
  exec_id=$(start_count_query "$table" "$partition" 2>/dev/null) || exec_id="FAILED"
  EXEC_IDS+=("$exec_id")
done

# Wait for all queries and save results
echo "Waiting for results..."
for i in "${!TABLES[@]}"; do
  table="${TABLES[$i]%%:*}"
  wait_and_save "${EXEC_IDS[$i]}" "${TMPDIR}/${table}.txt" &
done
wait
echo

# Print tables by layer
print_table "── Bronze ─────────────────────────────────" \
  "bronze_statcast:${TMPDIR}/bronze_statcast.txt"

print_table "── Silver ─────────────────────────────────" \
  "silver_pitches:${TMPDIR}/silver_pitches.txt" \
  "silver_pitches_staging:${TMPDIR}/silver_pitches_staging.txt" \
  "silver_teams:${TMPDIR}/silver_teams.txt" \
  "silver_venues:${TMPDIR}/silver_venues.txt" \
  "silver_games:${TMPDIR}/silver_games.txt" \
  "silver_umpires:${TMPDIR}/silver_umpires.txt" \
  "silver_players:${TMPDIR}/silver_players.txt"

print_table "── Gold ───────────────────────────────────" \
  "gold_pitches_shape_season:${TMPDIR}/gold_pitches_shape_season.txt" \
  "gold_pitch_type_norm_stats:${TMPDIR}/gold_pitch_type_norm_stats.txt" \
  "gold_repertoire_shape_neighbors:${TMPDIR}/gold_repertoire_shape_neighbors.txt" \
  "gold_catalog:${TMPDIR}/gold_catalog.txt"

# DynamoDB scans
echo "── DynamoDB (${SERVING_TABLE}) ──────────────────"
echo "Scanning DynamoDB (this may take a moment)..."
dynamo_count "pitch" "${TMPDIR}/dynamo_pitch.txt" &
dynamo_count "neighbor" "${TMPDIR}/dynamo_neighbor.txt" &
dynamo_count "catalog" "${TMPDIR}/dynamo_catalog.txt" &
wait
echo

print_table "── DynamoDB ───────────────────────────────" \
  "pitch:${TMPDIR}/dynamo_pitch.txt" \
  "neighbor:${TMPDIR}/dynamo_neighbor.txt" \
  "catalog:${TMPDIR}/dynamo_catalog.txt"

echo "=== Done ==="
