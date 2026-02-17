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
  frontend_domain_name  = var.frontend_domain_name
  hosted_zone_name      = var.hosted_zone_name
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito user pool"
  value       = module.doubleday.cognito_user_pool_id
}

output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = module.doubleday.cloudfront_distribution_id
}

output "frontend_bucket_name" {
  description = "Name of the S3 bucket for frontend assets"
  value       = module.doubleday.frontend_bucket_name
}

output "cognito_client_id" {
  description = "ID of the main Cognito client"
  value       = module.doubleday.cognito_client_id
}

output "frontend_url" {
  description = "URL of the frontend"
  value       = module.doubleday.frontend_url
}
