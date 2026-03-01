# Testing

## Unit tests

```bash
make test
```

## Integration tests

Integration tests run against live AWS resources in the dev environment. They require valid AWS credentials.

```bash
make test-integration
```

There are three flavors of API integration test:

| Test file | What it exercises | Auth? |
|---|---|---|
| `test_query_pitches_synthetic.py` | Lambda handler directly with synthetic events | No |
| `test_query_pitches_gateway.py` | API Gateway routing via `test-invoke-method` | No (bypassed) |
| `test_query_pitches_auth.py` | Full HTTPS request with Cognito JWT + API key | Yes |

The auth tests (`test_query_pitches_auth.py`) require a test Cognito user and credentials stored in Secrets Manager. See [Integration test setup](#integration-test-setup) for details.

Pipeline integration tests (`test_silver_pitches_load.py`) clear the test partition (`season=2024/game_date=2024-03-01`) from both staging and canonical before running, so they are safe to re-run.

## Integration test setup

The auth integration tests authenticate against a dedicated Cognito test client using `USER_PASSWORD_AUTH`. This requires one-time manual setup after deploying the test client with Terraform:

1. **Deploy the test client** — `terraform apply` in dev (the composition module sets `enable_test_client = true`)

2. **Get IDs from Terraform outputs:**
   ```bash
   USER_POOL_ID=$(cd terraform/environments/dev && terraform output -raw cognito_user_pool_id)
   TEST_CLIENT_ID=$(cd terraform/environments/dev && terraform output -raw cognito_test_client_id)
   API_KEY=$(cd terraform/environments/dev && terraform output -raw api_key)
   ```

3. **Create the test user:**
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id "$USER_POOL_ID" \
     --username "integration-test@doubleday.dev" \
     --user-attributes Name=email,Value=integration-test@doubleday.dev Name=email_verified,Value=true \
     --message-action SUPPRESS

   aws cognito-idp admin-set-user-password \
     --user-pool-id "$USER_POOL_ID" \
     --username "integration-test@doubleday.dev" \
     --password "<your-chosen-password>" \
     --permanent
   ```

4. **Create the Secrets Manager secret:**
   ```bash
   aws secretsmanager create-secret \
     --name "dev/doubleday/cognito_identity_provider/integration_test_credentials" \
     --secret-string '{
       "user_pool_id": "'"$USER_POOL_ID"'",
       "test_client_id": "'"$TEST_CLIENT_ID"'",
       "test_email": "integration-test@doubleday.dev",
       "test_password": "<your-chosen-password>",
       "api_key": "'"$API_KEY"'",
       "api_url": "https://api.doubleday-dev.appleforge.com"
     }'
   ```

The test client is only created in dev (`enable_test_client = true`). Prod defaults to `false` — no test client, no change.
