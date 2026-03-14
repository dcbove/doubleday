# Doubleday — Claude Code Guidelines

## Docstrings

Every Python module and every public function/class/method must have a docstring.
Use Google-style docstrings. This is enforced by Ruff (`D` rules, `convention = "google"`).

## Python Environment

All Python commands must be run through `uv run` (e.g., `uv run ruff check`, `uv run pytest`, `uv run mypy`). Do not invoke Python tools directly — `uv run` ensures the correct virtualenv and dependencies are used.

## Linting

Run `uv run ruff check` before committing. Fix any violations — do not suppress with `noqa` unless discussed.

## Testing

Run unit tests with `uv run pytest tests/unit/`. Do not run integration tests (`tests/integration/`) — they require live AWS resources and credentials.

## Deployment

Do not deploy directly. Deployment is handled by CI/CD (see `docs/INFRASTRUCTURE.md`). When changes are ready, suggest that the user commit, push, and open a PR. Provide suggested commands but let the user execute them.

## Documentation

| File | Description |
|------|-------------|
| `docs/ARCHITECTURE.md` | Design rationale for key architectural choices (partition strategy, Iceberg, etc.) |
| `docs/API.md` | REST API reference — domain layout, endpoints, auth, rate limiting |
| `docs/DATALAKE.md` | Data lake layers, table definitions, S3 layout, Iceberg storage |
| `docs/INFRASTRUCTURE.md` | Terraform modules, Lambda packaging, CI/CD deployment flow |
| `docs/OPERATIONS.md` | Runbook for invoking Lambdas, running scripts, managing data sources |
| `docs/PIPELINE.md` | Step Function orchestration, Lambda functions, data flow |
| `docs/RELEASE.md` | iOS release guide — EAS builds, TestFlight, App Store submission |
| `docs/STRIPE.md` | Stripe integration design — subscriptions, webhooks, entitlements |
| `docs/TESTING.md` | Test commands, unit/integration test patterns |
| `docs/openapi.yaml` | OpenAPI 3.0 spec for the REST API |
| `terraform/CLAUDE.md` | Detailed Terraform architecture and conventions |

## Project Architecture

Statcast ETL pipeline: Bronze (raw CSV) → Silver (typed Iceberg) → Gold (aggregated Iceberg). Orchestrated by a Step Function, all serverless on AWS. REST API layer serves gold table data. Cognito handles authentication (Google federation); Stripe subscriptions + a DynamoDB entitlements table handle authorization. Data endpoints (pitches, neighbors) require an active subscription; catalog is free.

### Pipeline Lambda Pattern

Each pipeline Lambda lives in `src/doubleday/pipeline/<name>/` with:
- `__init__.py` — module docstring only
- `handler.py` — Lambda entry point. Parses event, calls pipeline, emits Powertools metrics, returns `{statusCode, body}`. Module-level clients/config from env vars.
- `pipeline.py` — Business logic. Returns a `@dataclass LoadResult`. No Lambda runtime dependencies. Exception: `validate_input` and `clear_staging` have no pipeline (logic is simple enough for handler alone).

### API Lambda Pattern

Each API Lambda lives in `src/doubleday/api/<name>/` with:
- `__init__.py` — module docstring only
- `handler.py` — API Gateway proxy handler. Parses path/query params, calls query module, returns `{statusCode, headers, body}` with CORS headers.
- `query.py` — Business logic. Returns a `@dataclass` result. Exceptions: `authorizer`, `stripe_webhook`, `create_checkout`, `customer_portal`, and `subscription_status` have no query module (logic is simple enough for handler alone).

### Terraform Pattern

- **Composition module** (`terraform/modules/doubleday/`): Wires all child modules together and builds the shared Lambda zip. Environments call this single module.
- **Pipeline modules** (`terraform/modules/pipeline/`): s3, glue, lambda, step_function. Lambda functions receive the shared zip as variables.
- **Cognito module** (`terraform/modules/cognito/`): User pool with Google federation. Optional test client (`enable_test_client`) for integration testing via `USER_PASSWORD_AUTH`.
- **API module** (`terraform/modules/api/`): API Gateway, authorizer Lambda, query Lambdas, subscription/Stripe Lambdas, entitlements DynamoDB table, custom domain, rate limiting. Each endpoint is a self-contained `.tf` file (Lambda + IAM + API GW resources + CORS).
- **Frontend module** (`terraform/modules/frontend/`): S3 + CloudFront + OAC + domain. SPA takes the root domain; API moves to `api.` subdomain.
- **OIDC module** (`terraform/modules/oidc/`): GitHub Actions IAM role via OIDC federation. Lives in its own root module (`terraform/environments/oidc/`) with separate state, applied before dev/prod in CI.
- **Environments** (`terraform/environments/{dev,prod}/main.tf`): Call `module "doubleday"` and pass variables.
- See `terraform/CLAUDE.md` for detailed Terraform architecture and conventions.

### Test Pattern

- Unit tests in `tests/unit/`, mirroring the source structure: `tests/unit/api/`, `tests/unit/pipeline/`, `tests/unit/util/`.
- Integration tests in `tests/integration/`. API integration tests have three tiers:
  - **Synthetic** (`test_query_pitches_synthetic.py`): invoke the Lambda handler directly with crafted events.
  - **Gateway** (`test_query_pitches_gateway.py`): use `test-invoke-method` to exercise API Gateway routing without auth.
  - **Auth** (`test_query_pitches_auth.py`): full HTTPS requests with a real Cognito JWT and API key. Credentials are read from Secrets Manager (`dev/doubleday/cognito_identity_provider/integration_test_credentials`).
- Use `MagicMock` for AWS clients, `@patch` for module-level functions (e.g., `doubleday.pipeline.<name>.pipeline.run_query`).
- Fixtures with `tmp_path` for SQL template files.
- For `botocore.exceptions.ClientError` mocking: import the real exception class and set `s3.exceptions.ClientError = ClientError` on the mock.

### Frontend Pattern

Expo React Native app in `frontend/` targeting iOS, Android, and web from a single codebase. Stack: Expo SDK 54, Expo Router (file-based routing), NativeWind v4 (Tailwind CSS 3.x for React Native), react-native-svg, Amplify v6 (auth only). Plain JavaScript, not TypeScript.

- Routes in `frontend/app/` — Expo Router file-based routing. Protected routes under `app/(auth)/`.
- Shared UI in `frontend/src/components/<Name>.jsx`.
- Auth via `frontend/src/auth/` — Amplify Cognito PKCE flow with Google federation. `AuthProvider.jsx` wraps the app, `useAuth.js` hook exposes `user`, `login`, `logout`, `getAccessToken`. Platform-aware redirect URIs in `amplifyConfig.js` (web uses HTTPS URLs, mobile uses `doubleday://` deep links).
- API calls via `frontend/src/api/client.js` — `fetch` wrapper that injects Bearer token. On web, calls CloudFront URL (which proxies `/api/*` to API Gateway and injects `x-api-key`). On mobile, calls API directly with `x-api-key` header.
- Env vars use `EXPO_PUBLIC_*` prefix (read by Metro bundler at build time).
- Local dev: `npx expo start --web` (port 8081) against deployed CloudFront backend (`EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_CDN_ORIGIN`).
- Web production build: `npx expo export --platform web` → outputs to `dist/`.
- Charts use `react-native-svg` (`Svg`, `Circle`, `Ellipse`, `Line`, `Text as SvgText`). Tap-to-toggle replaces mouse hover for pitch type selection.
- Catalog caching uses `@react-native-async-storage/async-storage` (replaces `localStorage`).
- **Frontend module** (`terraform/modules/frontend/`): S3 bucket (OAC), CloudFront distribution, CF Function to strip `/api` prefix, ACM cert, Route53 record. S3 CORS configured for `localhost:8081` (local dev cross-origin static file access).

### Domain Layout

- `doubleday-{env}.appleforge.com` — CloudFront → S3 (SPA). Proxies `/api/*` to API Gateway, injecting `x-api-key`.
- `api.doubleday-{env}.appleforge.com` — API Gateway directly (for non-browser clients, requires `x-api-key` header).

### Key Paths

- Pipeline SQL templates: `sql/pipeline/` (bundled into Lambda zip as `doubleday/sql/pipeline/`)
- DDL: `sql/ddl/`
- Shared utilities: `src/doubleday/util/` (`athena.py`, `entitlements.py`)
- Lambda packages: Bazel builds per-Lambda zips (`bazel build //src/doubleday/...`); `scripts/copy_lambda_zips.sh` copies to `builds/lambdas/`; `terraform/modules/doubleday/package.tf` references them. Pip deps (PyJWT, cryptography, stripe) are in a separate Lambda Layer
- API code: `src/doubleday/api/`
- Pipeline code: `src/doubleday/pipeline/`
- Frontend routes: `frontend/app/` (Expo Router file-based)
- Frontend code: `frontend/src/`
