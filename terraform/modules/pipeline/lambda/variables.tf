variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "glue_database" {
  description = "Glue catalog database name"
  type        = string
}

variable "athena_results_bucket" {
  description = "S3 bucket name for Athena query results"
  type        = string
}

variable "lakehouse_bucket_arn" {
  description = "ARN of the lakehouse S3 bucket"
  type        = string
}

variable "lakehouse_bucket_name" {
  description = "Name of the lakehouse S3 bucket"
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

variable "frontend_bucket_name" {
  description = "Name of the frontend S3 bucket"
  type        = string
}

variable "frontend_bucket_arn" {
  description = "ARN of the frontend S3 bucket"
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
