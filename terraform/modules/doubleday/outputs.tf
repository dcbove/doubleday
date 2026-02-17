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

output "cognito_user_pool_id" {
  description = "ID of the Cognito user pool"
  value       = module.cognito.user_pool_id
}

output "cognito_test_client_id" {
  description = "ID of the test Cognito client (empty when disabled)"
  value       = module.cognito.test_client_id
}
