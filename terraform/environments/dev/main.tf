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
  cognito_callback_urls = var.cognito_callback_urls
  cognito_logout_urls   = var.cognito_logout_urls
  api_domain_name       = var.api_domain_name
  hosted_zone_name      = var.hosted_zone_name
}

module "oidc" {
  source                = "../../modules/oidc"
  project               = var.project
  region                = var.region
  github_repo           = "dcbove/doubleday"
  state_bucket          = "appleforge-terraform-state"
  lock_table            = "appleforge-terraform-locks"
  athena_results_bucket = var.athena_results_bucket
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions OIDC role"
  value       = module.oidc.role_arn
}
