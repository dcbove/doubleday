provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
    }
  }
}

module "doubleday" {
  source                = "../../modules/doubleday"
  project               = var.project
  environment           = var.environment
  region                = var.region
  athena_results_bucket = var.athena_results_bucket
  powertools_layer_arn  = var.powertools_layer_arn
  google_client_id      = var.google_client_id
  google_client_secret  = var.google_client_secret
  cognito_callback_urls = var.cognito_callback_urls
  cognito_logout_urls   = var.cognito_logout_urls
  api_domain_name       = var.api_domain_name
  hosted_zone_name      = var.hosted_zone_name
}
