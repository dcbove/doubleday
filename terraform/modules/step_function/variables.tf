variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "silver_load_function_arn" {
  description = "ARN of the silver load Lambda function"
  type        = string
}

variable "gold_load_function_arn" {
  description = "ARN of the gold load Lambda function"
  type        = string
}

variable "bronze_load_function_arn" {
  description = "ARN of the bronze load Lambda function"
  type        = string
}

variable "validate_input_function_arn" {
  description = "ARN of the validate input Lambda function"
  type        = string
}
