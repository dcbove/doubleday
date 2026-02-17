output "api_url" {
  description = "URL of the API Gateway stage"
  value       = aws_api_gateway_stage.main.invoke_url
}

output "custom_domain_url" {
  description = "Custom domain URL for the API"
  value       = "https://${aws_api_gateway_domain_name.main.domain_name}"
}

output "api_key" {
  description = "API key for rate-limited access"
  value       = aws_api_gateway_api_key.main.value
  sensitive   = true
}
