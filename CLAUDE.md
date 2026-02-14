# Doubleday — Claude Code Guidelines

## Docstrings

Every Python module and every public function/class/method must have a docstring.
Use Google-style docstrings. This is enforced by Ruff (`D` rules, `convention = "google"`).

## Linting

Run `ruff check` before committing. Fix any violations — do not suppress with `noqa` unless discussed.

## Project Architecture

Statcast ETL pipeline: Bronze (raw CSV) → Silver (typed Iceberg) → Gold (aggregated Iceberg). Orchestrated by a Step Function, all serverless on AWS.

### Lambda Pattern

Each Lambda lives in `src/doubleday/lambdas/<name>/` with:
- `__init__.py` — module docstring only
- `handler.py` — Lambda entry point. Parses event, calls pipeline, emits Powertools metrics, returns `{statusCode, body}`. Module-level clients/config from env vars.
- `pipeline.py` — Business logic. Returns a `@dataclass LoadResult`. No Lambda runtime dependencies. Exception: `validate_input` and `clear_staging` have no pipeline (logic is simple enough for handler alone).

### Terraform Pattern

- **Lambda module** (`terraform/modules/lambda/`): One `.tf` file per Lambda with IAM role + policy + `aws_lambda_function`. All share a single zip from `package.tf`. Outputs: `<name>_function_arn` and `<name>_function_name`.
- **Step Function module** (`terraform/modules/step_function/`): IAM policy lists all Lambda ARNs. State machine definition uses `jsonencode()` inline.
- **Environments** (`terraform/environments/{dev,prod}/main.tf`): Wire module outputs → inputs. Dev has OIDC module; prod does not.

### Test Pattern

- Unit tests in `tests/test_<name>.py`. Integration tests in `tests/integration/`.
- Use `MagicMock` for AWS clients, `@patch` for module-level functions (e.g., `doubleday.lambdas.<name>.pipeline.run_query`).
- Fixtures with `tmp_path` for SQL template files.
- For `botocore.exceptions.ClientError` mocking: import the real exception class and set `s3.exceptions.ClientError = ClientError` on the mock.

### Key Paths

- SQL templates: `sql/pipeline/` (bundled into Lambda zip as `doubleday/sql/`)
- DDL: `sql/ddl/`
- Shared utilities: `src/doubleday/util/athena.py`
- Lambda package: `terraform/modules/lambda/package.tf` bundles `src/doubleday/**/*.py` + `sql/pipeline/*.sql`
