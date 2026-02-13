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

variable "powertools_layer_arn" {
  description = "ARN of the AWS Lambda Powertools for Python layer"
  type        = string
}
