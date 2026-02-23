#!/usr/bin/env bash
# Build the Lambda Layer package containing pip dependencies (PyJWT, cryptography).
# Separated from the code package so dependency changes (rare) don't slow down
# every source-code deploy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

rm -rf builds/lambda_layer
mkdir -p builds/lambda_layer/python

pip install PyJWT==2.11.0 cryptography==46.0.5 \
  --target builds/lambda_layer/python \
  --platform manylinux2014_x86_64 \
  --only-binary=:all: \
  --python-version 3.12 \
  --quiet

cd builds/lambda_layer
zip -r -q ../lambda_layer.zip python/

cd ..
echo "Lambda layer zip directory: $(pwd)"
ls -la lambda_layer.zip
