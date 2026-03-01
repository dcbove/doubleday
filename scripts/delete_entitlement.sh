#!/usr/bin/env bash
set -euo pipefail

LOOKUP=${1:?Usage: delete_entitlement.sh <email-or-cognito-sub> [environment]}
ENV=${2:-dev}

TABLE="doubleday-${ENV}-entitlements"

# If the lookup value contains '@', search by email; otherwise treat as cognito sub
if [[ "$LOOKUP" == *@* ]]; then
  echo "Scanning ${TABLE} for email=${LOOKUP}..."
  ITEM=$(aws dynamodb scan \
    --table-name "$TABLE" \
    --filter-expression "email = :val" \
    --expression-attribute-values "{\":val\": {\"S\": \"${LOOKUP}\"}}" \
    --query "Items[0]" \
    --output json)
else
  echo "Looking up ${TABLE} for USER#${LOOKUP}..."
  ITEM=$(aws dynamodb get-item \
    --table-name "$TABLE" \
    --key "{\"PK\": {\"S\": \"USER#${LOOKUP}\"}}" \
    --query "Item" \
    --output json)
fi

if [ "$ITEM" = "null" ] || [ -z "$ITEM" ]; then
  # Fall back to scanning all items if email lookup failed (email may be null)
  if [[ "$LOOKUP" == *@* ]]; then
    echo "Email lookup failed (field may be null). Listing all entitlements:"
    aws dynamodb scan \
      --table-name "$TABLE" \
      --query "Items[].{PK: PK.S, status: status.S, email: email}" \
      --output table
  fi
  echo "No entitlement found for ${LOOKUP}"
  exit 1
fi

PK=$(echo "$ITEM" | python3 -c "import sys,json; print(json.load(sys.stdin)['PK']['S'])")
STATUS=$(echo "$ITEM" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',{}).get('S','unknown'))")
STRIPE_SUB=$(echo "$ITEM" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stripe_subscription_id',{}).get('S',''))")

echo "Found: PK=${PK}, status=${STATUS}, subscription=${STRIPE_SUB}"

if [ -n "$STRIPE_SUB" ]; then
  echo ""
  echo "WARNING: Stripe subscription ${STRIPE_SUB} may still be active."
  echo "Cancel it in Stripe Dashboard or run: stripe subscriptions cancel ${STRIPE_SUB}"
  echo ""
fi

read -rp "Delete this entitlement? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

aws dynamodb delete-item \
  --table-name "$TABLE" \
  --key "{\"PK\": {\"S\": \"${PK}\"}}"

echo "Deleted entitlement for ${LOOKUP} (${PK})"
