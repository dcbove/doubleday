data "aws_secretsmanager_secret_version" "google_oauth" {
  secret_id = "${var.environment}/doubleday/cognito_identity_provider/google_client_id"
}

locals {
  google_oauth = jsondecode(data.aws_secretsmanager_secret_version.google_oauth.secret_string)
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

module "lambda" {
  source                = "../pipeline/lambda"
  project               = var.project
  environment           = var.environment
  glue_database         = module.glue.database_name
  athena_results_bucket = var.athena_results_bucket
  lakehouse_bucket_arn  = module.s3.lakehouse_bucket_arn
  lakehouse_bucket_name = module.s3.lakehouse_bucket_name
  powertools_layer_arn  = var.powertools_layer_arn
  lambda_package_path   = data.archive_file.lambda_package.output_path
  lambda_package_hash   = data.archive_file.lambda_package.output_base64sha256
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
}

module "cognito" {
  source               = "../cognito"
  project              = var.project
  environment          = var.environment
  google_client_id     = local.google_oauth["google_client_id"]
  google_client_secret = local.google_oauth["google_client_secret"]
  callback_urls        = var.cognito_callback_urls
  logout_urls          = var.cognito_logout_urls
}

module "api" {
  source                = "../api"
  project               = var.project
  environment           = var.environment
  region                = var.region
  glue_database         = module.glue.database_name
  athena_results_bucket = var.athena_results_bucket
  lakehouse_bucket_arn  = module.s3.lakehouse_bucket_arn
  powertools_layer_arn  = var.powertools_layer_arn
  lambda_package_path   = data.archive_file.lambda_package.output_path
  lambda_package_hash   = data.archive_file.lambda_package.output_base64sha256
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_user_pool_arn = module.cognito.user_pool_arn
  cognito_client_id     = module.cognito.client_id
  domain_name           = var.api_domain_name
  hosted_zone_name      = var.hosted_zone_name
}
