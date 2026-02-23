variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "state_machine_arn" {
  description = "ARN of the pipeline Step Function to trigger"
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

variable "powertools_layer_arn" {
  description = "ARN of the AWS Lambda Powertools for Python layer"
  type        = string
}

variable "deps_layer_arn" {
  description = "ARN of the Lambda Layer containing pip dependencies (PyJWT, cryptography)"
  type        = string
}
