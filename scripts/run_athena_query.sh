#!/usr/bin/env bash
set -euo pipefail

SQL_FILE=${1:?Usage: run_athena_query.sh <sql_file> <database> <output_bucket> [lakehouse_bucket] [workgroup]}
DATABASE=${2:?Usage: run_athena_query.sh <sql_file> <database> <output_bucket> [lakehouse_bucket] [workgroup]}
OUTPUT_BUCKET=${3:?Usage: run_athena_query.sh <sql_file> <database> <output_bucket> [lakehouse_bucket] [workgroup]}
LAKEHOUSE_BUCKET=${4:-}
WORKGROUP=${5:-primary}

QUERY=$(cat "$SQL_FILE")

if [ -n "$LAKEHOUSE_BUCKET" ]; then
  QUERY=${QUERY//\{lakehouse_bucket\}/$LAKEHOUSE_BUCKET}
fi

EXECUTION_ID=$(aws athena start-query-execution \
  --query-string "$QUERY" \
  --work-group "$WORKGROUP" \
  --query-execution-context "Database=${DATABASE}" \
  --result-configuration "OutputLocation=s3://${OUTPUT_BUCKET}/" \
  --output text --query 'QueryExecutionId')

echo "Query execution ID: $EXECUTION_ID"

while true; do
  STATUS=$(aws athena get-query-execution \
    --query-execution-id "$EXECUTION_ID" \
    --output text --query 'QueryExecution.Status.State')

  case "$STATUS" in
    SUCCEEDED)
      echo "Query succeeded."
      exit 0
      ;;
    FAILED|CANCELLED)
      REASON=$(aws athena get-query-execution \
        --query-execution-id "$EXECUTION_ID" \
        --output text --query 'QueryExecution.Status.StateChangeReason')
      echo "Query ${STATUS}: ${REASON}" >&2
      exit 1
      ;;
    *)
      sleep 2
      ;;
  esac
done
