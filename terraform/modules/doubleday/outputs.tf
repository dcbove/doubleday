output "api_url" {
  description = "URL of the API Gateway stage"
  value       = module.api.api_url
}

output "custom_domain_url" {
  description = "Custom domain URL for the API"
  value       = module.api.custom_domain_url
}

output "api_key" {
  description = "API key for rate-limited access"
  value       = module.api.api_key
  sensitive   = true
}
