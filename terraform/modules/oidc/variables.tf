variable "project" {
  description = "Project name used for resource naming"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format"
  type        = string
}

variable "state_bucket" {
  description = "S3 bucket name for Terraform state"
  type        = string
}

variable "lock_table" {
  description = "DynamoDB table name for Terraform state locking"
  type        = string
}

variable "athena_results_bucket" {
  description = "S3 bucket name for Athena query results"
  type        = string
}
