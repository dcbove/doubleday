provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
    }
  }
}

module "s3" {
  source      = "../../modules/s3"
  project     = var.project
  environment = var.environment
}

module "glue" {
  source                = "../../modules/glue"
  project               = var.project
  environment           = var.environment
  lakehouse_bucket_name = module.s3.lakehouse_bucket_name
  athena_results_bucket = var.athena_results_bucket
}

module "lambda" {
  source                = "../../modules/lambda"
  project               = var.project
  environment           = var.environment
  glue_database         = module.glue.database_name
  athena_results_bucket = var.athena_results_bucket
  lakehouse_bucket_arn  = module.s3.lakehouse_bucket_arn
  powertools_layer_arn  = var.powertools_layer_arn
}

module "step_function" {
  source                   = "../../modules/step_function"
  project                  = var.project
  environment              = var.environment
  silver_load_function_arn = module.lambda.silver_load_function_arn
  gold_load_function_arn   = module.lambda.gold_load_function_arn
}
