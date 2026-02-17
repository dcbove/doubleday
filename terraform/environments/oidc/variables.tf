variable "project" {
  description = "Project name"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "athena_results_bucket" {
  description = "S3 bucket for Athena query results"
  type        = string
}
