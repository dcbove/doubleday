variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "lakehouse_bucket_name" {
  description = "Name of the lakehouse S3 bucket"
  type        = string
}

variable "athena_results_bucket" {
  description = "S3 bucket name for Athena query results"
  type        = string
}
