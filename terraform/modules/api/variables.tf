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

variable "serving_table_name" {
  description = "Name of the DynamoDB serving table"
  type        = string
}

variable "serving_table_arn" {
  description = "ARN of the DynamoDB serving table"
  type        = string
}

variable "powertools_layer_arn" {
  description = "ARN of the AWS Lambda Powertools for Python layer"
  type        = string
}

variable "deps_layer_arn" {
  description = "ARN of the Lambda Layer containing pip dependencies (PyJWT, cryptography)"
  type        = string
}

variable "lambda_packages" {
  description = "Map of Lambda name to {path, hash} for per-Lambda zip files"
  type = map(object({
    path = string
    hash = string
  }))
}

variable "cognito_user_pool_id" {
  description = "ID of the Cognito user pool"
  type        = string
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito user pool"
  type        = string
}

variable "cognito_client_ids" {
  description = "IDs of the Cognito user pool clients (main + optional test)"
  type        = list(string)
}

variable "domain_name" {
  description = "Custom domain name for the API (e.g. doubleday-dev.appleforge.com)"
  type        = string
}

variable "hosted_zone_name" {
  description = "Route53 hosted zone name (e.g. appleforge.com)"
  type        = string
}

variable "frontend_bucket_name" {
  description = "Name of the frontend S3 bucket (for catalog manifest reads)"
  type        = string
}

variable "frontend_bucket_arn" {
  description = "ARN of the frontend S3 bucket (for catalog manifest IAM policy)"
  type        = string
}

variable "rate_limit" {
  description = "Steady-state request rate limit per second"
  type        = number
  default     = 50
}

variable "burst_limit" {
  description = "Burst request rate limit"
  type        = number
  default     = 100
}

variable "enable_stripe" {
  description = "Whether to create Stripe integration resources (EventBridge, checkout, portal)"
  type        = bool
  default     = true
}

variable "stripe_secret_key" {
  description = "Stripe secret API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "stripe_event_source_name" {
  description = "Stripe EventBridge partner event source name (e.g. aws.partner/stripe.com/<account_id>/<destination_id>)"
  type        = string
  default     = ""
}

variable "stripe_price_id" {
  description = "Stripe Price ID for the subscription plan"
  type        = string
  default     = ""
}

variable "frontend_url" {
  description = "Frontend URL for Stripe redirect URLs (e.g. https://doubleday-dev.appleforge.com)"
  type        = string
}
