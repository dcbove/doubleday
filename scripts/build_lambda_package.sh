#!/usr/bin/env bash
# Build the Lambda deployment package (deps + source + SQL).
# Single source of truth — called by CI workflows and terraform (package.tf).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

rm -rf builds/lambda_deps builds/lambda_package
mkdir -p builds/lambda_package/doubleday/sql/pipeline builds/lambda_package/doubleday/sql/api

pip install PyJWT cryptography \
  --target builds/lambda_deps \
  --platform manylinux2014_x86_64 \
  --only-binary=:all: \
  --python-version 3.12 \
  --quiet

cp -r builds/lambda_deps/* builds/lambda_package/

(cd src && find doubleday -name '*.py' | while IFS= read -r f; do
  mkdir -p "../builds/lambda_package/$(dirname "$f")"
  cp "$f" "../builds/lambda_package/$f"
done)

cp sql/pipeline/*.sql builds/lambda_package/doubleday/sql/pipeline/
cp sql/api/*.sql builds/lambda_package/doubleday/sql/api/
