data "aws_secretsmanager_secret_version" "google_oauth" {
  secret_id = "${var.environment}/doubleday/cognito_identity_provider/google_client_id"
}

data "aws_secretsmanager_secret_version" "stripe_api_keys" {
  count     = var.enable_stripe ? 1 : 0
  secret_id = "${var.environment}/doubleday/stripe/api_keys"
}

locals {
  google_oauth         = jsondecode(data.aws_secretsmanager_secret_version.google_oauth.secret_string)
  stripe_api_keys      = var.enable_stripe ? jsondecode(data.aws_secretsmanager_secret_version.stripe_api_keys[0].secret_string) : {}
  frontend_bucket_name = "${var.project}-${var.environment}-frontend"
  frontend_bucket_arn  = "arn:aws:s3:::${var.project}-${var.environment}-frontend"
}

module "s3" {
  source      = "../pipeline/s3"
  project     = var.project
  environment = var.environment
}

module "glue" {
  source                = "../pipeline/glue"
  project               = var.project
  environment           = var.environment
  lakehouse_bucket_name = module.s3.lakehouse_bucket_name
  athena_results_bucket = var.athena_results_bucket
}

module "dynamodb" {
  source      = "../pipeline/dynamodb"
  project     = var.project
  environment = var.environment
}

module "lambda" {
  source                = "../pipeline/lambda"
  project               = var.project
  environment           = var.environment
  glue_database         = module.glue.database_name
  athena_results_bucket = var.athena_results_bucket
  lakehouse_bucket_arn  = module.s3.lakehouse_bucket_arn
  lakehouse_bucket_name = module.s3.lakehouse_bucket_name
  powertools_layer_arn  = var.powertools_layer_arn
  deps_layer_arn        = aws_lambda_layer_version.deps.arn
  lambda_package_path   = data.archive_file.lambda_package.output_path
  lambda_package_hash   = data.archive_file.lambda_package.output_base64sha256
  frontend_bucket_name  = module.frontend.frontend_bucket_name
  frontend_bucket_arn   = module.frontend.frontend_bucket_arn
  serving_table_name    = module.dynamodb.table_name
  serving_table_arn     = module.dynamodb.table_arn
}

module "step_function" {
  source                      = "../pipeline/step_function"
  project                     = var.project
  environment                 = var.environment
  silver_load_function_arn    = module.lambda.silver_load_function_arn
  gold_load_function_arn      = module.lambda.gold_load_function_arn
  bronze_load_function_arn    = module.lambda.bronze_load_function_arn
  validate_input_function_arn = module.lambda.validate_input_function_arn
  clear_staging_function_arn  = module.lambda.clear_staging_function_arn
  check_failures_function_arn = module.lambda.check_failures_function_arn
  catalog_build_function_arn  = module.lambda.catalog_build_function_arn
  dynamodb_load_function_arn  = module.lambda.dynamodb_load_function_arn
}

module "schedule" {
  source               = "../pipeline/schedule"
  project              = var.project
  environment          = var.environment
  state_machine_arn    = module.step_function.state_machine_arn
  lambda_package_path  = data.archive_file.lambda_package.output_path
  lambda_package_hash  = data.archive_file.lambda_package.output_base64sha256
  powertools_layer_arn = var.powertools_layer_arn
  deps_layer_arn       = aws_lambda_layer_version.deps.arn
}

module "dashboard" {
  source      = "../pipeline/dashboard"
  project     = var.project
  environment = var.environment
  region      = var.region
}

module "cognito" {
  source               = "../cognito"
  project              = var.project
  environment          = var.environment
  google_client_id     = local.google_oauth["google_client_id"]
  google_client_secret = local.google_oauth["google_client_secret"]
  callback_urls        = var.cognito_callback_urls
  logout_urls          = var.cognito_logout_urls
  enable_test_client   = var.enable_test_client
}

module "api" {
  source              = "../api"
  project             = var.project
  environment         = var.environment
  region              = var.region
  serving_table_name  = module.dynamodb.table_name
  serving_table_arn   = module.dynamodb.table_arn
  powertools_layer_arn = var.powertools_layer_arn
  deps_layer_arn        = aws_lambda_layer_version.deps.arn
  lambda_package_path   = data.archive_file.lambda_package.output_path
  lambda_package_hash   = data.archive_file.lambda_package.output_base64sha256
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_user_pool_arn = module.cognito.user_pool_arn
  cognito_client_ids = compact([
    module.cognito.client_id,
    module.cognito.test_client_id,
  ])
  domain_name            = var.api_domain_name
  hosted_zone_name       = var.hosted_zone_name
  frontend_bucket_name   = local.frontend_bucket_name
  frontend_bucket_arn    = local.frontend_bucket_arn
  enable_stripe            = var.enable_stripe
  stripe_secret_key        = var.enable_stripe ? local.stripe_api_keys["secret_key"] : ""
  stripe_event_source_name = var.stripe_event_source_name
  stripe_price_id          = var.stripe_price_id
  frontend_url           = "https://${var.frontend_domain_name}"
}

module "frontend" {
  source           = "../frontend"
  project          = var.project
  environment      = var.environment
  domain_name      = var.frontend_domain_name
  hosted_zone_name = var.hosted_zone_name
  api_domain_name  = var.api_domain_name
  api_key          = module.api.api_key
}
