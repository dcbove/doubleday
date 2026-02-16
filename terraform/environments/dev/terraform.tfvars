project               = "doubleday"
environment           = "dev"
region                = "us-east-1"
athena_results_bucket = "appleforge-athena-query-results"
powertools_layer_arn  = "arn:aws:lambda:us-east-1:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:15"
api_domain_name       = "doubleday-dev.appleforge.com"
hosted_zone_name      = "appleforge.com"
cognito_callback_urls = ["http://localhost:3000/callback"]
cognito_logout_urls   = ["http://localhost:3000"]
# google_client_id and google_client_secret via env vars (TF_VAR_) or untracked .tfvars
