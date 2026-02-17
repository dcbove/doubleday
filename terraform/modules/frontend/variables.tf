variable "project" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment name used for resource naming and tagging"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name for the frontend (e.g. doubleday-dev.appleforge.com)"
  type        = string
}

variable "hosted_zone_name" {
  description = "Route53 hosted zone name (e.g. appleforge.com)"
  type        = string
}

variable "api_domain_name" {
  description = "Custom domain name for the API origin (e.g. api.doubleday-dev.appleforge.com)"
  type        = string
}

variable "api_key" {
  description = "API key injected as custom origin header for API Gateway"
  type        = string
  sensitive   = true
}
