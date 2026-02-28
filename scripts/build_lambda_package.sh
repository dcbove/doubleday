#!/usr/bin/env bash
# Build the Lambda deployment package (source + SQL only).
# Dependencies (PyJWT, cryptography) live in a separate Lambda Layer
# built by build_lambda_layer.sh!
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

rm -rf builds/lambda_package
mkdir -p builds/lambda_package/doubleday/sql/pipeline

(cd src && find doubleday -name '*.py' | while IFS= read -r f; do
  mkdir -p "../builds/lambda_package/$(dirname "$f")"
  cp "$f" "../builds/lambda_package/$f"
done)

cp sql/pipeline/*.sql builds/lambda_package/doubleday/sql/pipeline/
