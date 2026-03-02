# Infrastructure

Infrastructure is managed with Terraform with two environments (dev, prod) in the same AWS account.

```bash
cd terraform/environments/dev   # or prod
terraform init
terraform plan
terraform apply
```

## Modules

| Module | Description |
|--------|-------------|
| `doubleday` | Composition module — wires all child modules, builds the shared Lambda zip |
| `pipeline/s3` | Lakehouse S3 bucket |
| `pipeline/glue` | Glue database, bronze/silver/gold table DDL |
| `pipeline/lambda` | Pipeline Lambda functions (validate_input, bronze_load, silver_load, gold_load, dimension_load, dynamodb_load, catalog_build, clear_staging, check_failures), IAM roles |
| `pipeline/step_function` | Pipeline Step Function, IAM role, CloudWatch logging |
| `pipeline/schedule` | EventBridge Scheduler, daily_trigger Lambda (9 AM ET) |
| `pipeline/dashboard` | CloudWatch dashboard for pipeline metrics |
| `pipeline/dynamodb` | DynamoDB serving table |
| `cognito` | Cognito user pool with Google federation, hosted UI |
| `api` | API Gateway REST API, authorizer Lambda, query Lambda, custom domain, rate limiting |
| `frontend` | S3 bucket (OAC), CloudFront distribution, CF Function, ACM cert, Route53 |
| `oidc` | GitHub Actions OIDC provider and IAM role (dev only, account-level) |

Environment files (`dev/main.tf`, `prod/main.tf`) call `module "doubleday"` and pass variables — they never reference child modules directly. All inter-module wiring lives in the composition module.

All Lambda functions (pipeline and API) share a code zip built by the composition module (`doubleday/package.tf`). It bundles the full `doubleday` Python package from `src/` and SQL templates from `sql/pipeline/`. Pip dependencies (PyJWT, cryptography, stripe) are in a separate Lambda Layer that only rebuilds when dependencies change. Each Lambda points at the same code zip with a different handler entry point.

For fast iterative deploys during development, `scripts/deploy_lambda_code.sh` bypasses Terraform to push code changes directly — see [OPERATIONS.md](OPERATIONS.md#fast-lambda-code-deploy).

Each API endpoint is a self-contained `.tf` file in the `api` module containing its Lambda function, IAM role, API Gateway resources, and CORS configuration.

## Deployment

Infrastructure changes are deployed automatically via GitHub Actions using OIDC for AWS authentication (no long-lived credentials).

### CI/CD workflows

- **`terraform-plan.yml`** — runs on PRs that touch `terraform/`, `src/`, `sql/`, or `frontend/`. Applies dev (infra + frontend build/deploy) and plans prod (posting the plan as a PR comment).
- **`terraform-apply.yml`** — runs on push to `main` that touches `terraform/`, `src/`, `sql/`, or `frontend/`. Applies prod and deploys the frontend.

Dev is deployed during the PR lifecycle so changes can be tested before merging. Prod is deployed only after merging to `main`.

After Terraform apply, the CI pipeline builds the frontend (`npx expo export --platform web` with `EXPO_PUBLIC_*` env vars from Terraform outputs), syncs the dist to S3, and invalidates the CloudFront cache.

### Bootstrap (one-time setup)

The OIDC resources must exist before GitHub Actions can authenticate. To bootstrap:

1. `cd terraform/environments/dev && terraform apply` — creates the OIDC provider and IAM role
2. `cd terraform/environments/prod && terraform apply` — creates prod resources
3. Copy the OIDC role ARN from the `module.oidc.role_arn` output
4. Add it as the GitHub Actions secret `AWS_ROLE_ARN`

After bootstrap, PRs auto-deploy dev and merges to `main` auto-deploy prod.
