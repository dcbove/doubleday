# Development

Setup, commands, and conventions for working on Doubleday.

## Prerequisites

- **Python 3.13** via [pyenv](https://github.com/pyenv/pyenv)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Node.js** (for the frontend)
- **[Bazel](https://bazel.build/)** (for Lambda packaging)

```bash
brew install pyenv uv node
pyenv install 3.13
```

## Setup

```bash
git clone https://github.com/dcbove/doubleday.git
cd doubleday
make install
```

`make install` does three things:
1. Installs Python dependencies via `uv sync --dev`
2. Installs frontend npm dependencies
3. Configures the pre-commit hook (sets `core.hooksPath` to `.githooks/`)

## Commands

### Python

| Command | Description |
|---------|-------------|
| `make lint` | Lint and auto-fix with Ruff |
| `make format` | Format with Black |
| `make typecheck` | Type check with mypy |
| `make test` | Run unit tests (excludes integration) |
| `make test-integration` | Run integration tests (requires AWS credentials) |
| `make check-all` | Run all checks: lint, format, typecheck, unit tests |

All Python tools run through `uv run` (e.g., `uv run ruff check`, `uv run pytest`). The Makefile handles this — use `make` commands rather than invoking tools directly.

### Frontend

| Command | Description |
|---------|-------------|
| `make frontend-dev` | Start web dev server (`localhost:8081`) |
| `make frontend-ios` | Build and run on iOS simulator |
| `make frontend-build` | Production web build |
| `make frontend-deploy` | Build and deploy to S3/CloudFront (`ENV=dev\|prod`) |
| `make frontend-clean` | Remove `node_modules/` and `dist/` |

### Lambda Packaging

| Command | Description |
|---------|-------------|
| `bazel build //src/doubleday/...` | Build all per-Lambda zips |
| `scripts/copy_lambda_zips.sh` | Copy zips from `bazel-bin/` to `builds/lambdas/` |
| `scripts/build_lambda_layer.sh` | Build the pip dependencies Lambda Layer |

Bazel builds per-Lambda zips containing only each handler's transitive dependencies. `BUILD.bazel` files throughout `src/doubleday/` define the dependency graph — Bazel only rebuilds zips whose transitive deps changed.

### Other

| Command | Description |
|---------|-------------|
| `make clean` | Remove all cache files and build artifacts |
| `make install-hooks` | Re-install the pre-commit hook |
| `make help` | Show all available make targets |

## Pre-commit Hook

The pre-commit hook runs automatically on `git commit`. It:
1. Auto-fixes lint and formatting issues (Ruff + Black)
2. Re-stages the fixed files
3. Fails only on errors that can't be auto-fixed (type errors, test failures)

The hook lives in `.githooks/` (tracked in the repo). `make install` sets `core.hooksPath` — no extra tooling needed.

## Code Standards

- **Docstrings** — every Python module, public function, class, and method. Google-style convention, enforced by Ruff's `D` rules.
- **Linting** — Ruff with `B`, `D`, `E`, `F`, `I`, `UP` rule sets. Line length: 119.
- **Formatting** — Black. Line length: 119.
- **Type checking** — mypy with `warn_return_any` and `warn_unused_configs`.

## Project Layout

```
src/doubleday/
  pipeline/         # ETL Lambda functions (handler.py + pipeline.py per Lambda)
  api/              # API Lambda functions (handler.py + query.py per Lambda)
  util/             # Shared utilities (Athena, entitlements)
sql/
  ddl/              # Table DDL (Iceberg CREATE TABLE statements)
  pipeline/         # Pipeline SQL templates (INSERT, DELETE)
  api/              # API query SQL
terraform/
  modules/          # Reusable Terraform modules
  environments/     # Dev/prod/OIDC environment roots
frontend/
  app/              # Expo Router file-based routes
  src/              # Components, hooks, auth, API client
tests/
  unit/             # Unit tests (mirrors src/ structure)
  integration/      # Integration tests (requires AWS)
scripts/            # Build, deploy, and operational scripts
```

### Lambda Pattern

Handler code (`handler.py`) is separated from business logic (`pipeline.py` or `query.py`) so the logic can be tested and reused without a Lambda runtime.

- **Pipeline Lambdas** (`src/doubleday/pipeline/<name>/`): `handler.py` parses the Step Function event, calls the pipeline, emits Powertools metrics, returns `{statusCode, body}`.
- **API Lambdas** (`src/doubleday/api/<name>/`): `handler.py` parses API Gateway proxy event, calls the query module, returns `{statusCode, headers, body}` with CORS headers.

### Generating the Mobile Demo GIF

The README embeds a GIF of the mobile app. To regenerate from the source video:

```bash
ffmpeg -i docs/images/doubleday-iphone.mov -vf "fps=15,scale=320:-1" -loop 0 docs/images/doubleday-iphone.gif
```

### Test Pattern

- Unit tests use `MagicMock` for AWS clients and `@patch` for module-level functions
- Integration tests have three tiers: synthetic (Lambda handler directly), gateway (`test-invoke-method`), and auth (full HTTPS with Cognito JWT)
- See [TESTING.md](TESTING.md) for details
