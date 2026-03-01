variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "athena_results_bucket" {
  description = "S3 bucket name for Athena query results"
  type        = string
}

variable "powertools_layer_arn" {
  description = "ARN of the AWS Lambda Powertools for Python layer"
  type        = string
}

variable "api_domain_name" {
  description = "Custom domain name for the API"
  type        = string
}

variable "hosted_zone_name" {
  description = "Route53 hosted zone name"
  type        = string
}

variable "frontend_domain_name" {
  description = "Custom domain name for the frontend"
  type        = string
}

variable "cognito_callback_urls" {
  description = "Allowed callback URLs for Cognito client"
  type        = list(string)
}

variable "cognito_logout_urls" {
  description = "Allowed logout URLs for Cognito client"
  type        = list(string)
}

variable "stripe_price_id" {
  description = "Stripe Price ID for the subscription plan"
  type        = string
}
