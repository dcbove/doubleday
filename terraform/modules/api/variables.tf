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

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB serving table"
  type        = string
}

variable "dynamodb_table_arn" {
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

variable "lambda_package_path" {
  description = "Path to the shared Lambda deployment zip"
  type        = string
}

variable "lambda_package_hash" {
  description = "Base64-encoded SHA256 hash of the Lambda deployment zip"
  type        = string
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
