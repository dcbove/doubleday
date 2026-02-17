# Terraform Architecture

## Composition Module (`modules/doubleday/`)

All inter-module wiring lives in one place: `modules/doubleday/main.tf`. Environment files (`environments/{dev,prod}/main.tf`) call `module "doubleday"` and pass variables — they never reference child modules directly.

This means adding a new child module or changing how modules connect requires editing only `modules/doubleday/main.tf`, not every environment.

## OIDC Environment (`environments/oidc/`)

The GitHub Actions OIDC role lives in its own root module with a separate state file (`doubleday/oidc/terraform.tfstate`). This ensures the IAM role and its policies are always applied *before* dev or prod, since the role's permissions must be in place before Terraform can manage other resources.

Both GitHub Actions workflows (`terraform-plan.yml`, `terraform-apply.yml`) have an `apply-oidc` job that runs first, with dev/prod jobs depending on it via `needs: apply-oidc`.

When adding permissions for a new AWS resource type, update `modules/oidc/main.tf` — the OIDC environment will apply the policy change before dev/prod attempt to use those permissions.

## Lambda Packaging (`modules/doubleday/package.tf`)

A single shared zip (`builds/lambda_package.zip`) is built by the composition module and passed as `lambda_package_path` / `lambda_package_hash` variables to both `module.lambda` (pipeline) and `module.api`. The zip contains:

- All Python source (`src/doubleday/**/*.py`)
- Pipeline SQL templates (`sql/pipeline/*.sql` → `doubleday/sql/`)
- API SQL templates (`sql/api/*.sql` → `doubleday/sql/api/`)
- Pip dependencies (PyJWT, cryptography) built for `manylinux2014_x86_64`

The build uses `null_resource` provisioners because cryptography has binary `.so` files that require platform-specific pip install. Triggers ensure rebuilds happen when source, SQL, or dependency lists change.

All build artifacts go in the project root `builds/` directory (gitignored).

## API Module: Self-Contained Endpoints (`modules/api/`)

Each API endpoint is a single `.tf` file containing everything for that endpoint:

- **API Gateway resources** (resource tree, method, integration)
- **CORS preflight** (OPTIONS method, mock integration, response headers)
- **Lambda function** (function, IAM role/policy, invoke permission)

Shared API infra lives in separate files:
- `gateway.tf` — REST API, authorizer, deployment/stage, usage plan, API key
- `authorizer.tf` — authorizer Lambda + IAM
- `domain.tf` — ACM cert, Route53, custom domain mapping

The deployment triggers in `gateway.tf` explicitly list resources from all endpoint files.

## Adding a New Endpoint

1. Python: `src/doubleday/api/<name>/` (handler.py + pipeline.py)
2. SQL: `sql/api/<name>.sql`
3. Terraform: `terraform/modules/api/<name>.tf` (Lambda + IAM + API GW resources + CORS)
4. Add the new API GW resources to the deployment triggers in `gateway.tf`
5. No changes to environment files or the composition module

## Frontend Module (`modules/frontend/`)

S3 bucket with Origin Access Control, CloudFront distribution, CF Function, ACM cert, and Route53 record. The SPA takes the root domain (`doubleday-{env}.appleforge.com`); the API lives at `api.doubleday-{env}.appleforge.com`.

CloudFront has two behaviors:
- Default (`/*`) → S3 origin (static assets, compressed, cached)
- Ordered (`/api/*`) → API Gateway origin (no cache, CF Function strips `/api` prefix, `x-api-key` injected as custom origin header)

SPA client-side routing is handled by a CloudFront Function on the default behavior that rewrites non-file URIs (paths without a `.`) to `/index.html`.

The frontend is built and deployed by CI — not by Terraform. Terraform creates the bucket and distribution; GitHub Actions runs `npm run build` and `aws s3 sync`.

## Glue DDL (`modules/pipeline/glue/`)

Table creation uses `null_resource` + `local-exec` to run Athena DDL via `scripts/run_athena_query.sh`. The `filemd5()` trigger re-runs DDL only when the SQL file changes. The `working_dir` must resolve to the project root (`${path.module}/../../../..` from `modules/pipeline/glue/`).
