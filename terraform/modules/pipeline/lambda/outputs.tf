output "silver_load_function_name" {
  description = "Name of the silver load Lambda function"
  value       = aws_lambda_function.silver_load.function_name
}

output "silver_load_function_arn" {
  description = "ARN of the silver load Lambda function"
  value       = aws_lambda_function.silver_load.arn
}

output "gold_load_function_name" {
  description = "Name of the gold load Lambda function"
  value       = aws_lambda_function.gold_load.function_name
}

output "gold_load_function_arn" {
  description = "ARN of the gold load Lambda function"
  value       = aws_lambda_function.gold_load.arn
}

output "bronze_load_function_name" {
  description = "Name of the bronze load Lambda function"
  value       = aws_lambda_function.bronze_load.function_name
}

output "bronze_load_function_arn" {
  description = "ARN of the bronze load Lambda function"
  value       = aws_lambda_function.bronze_load.arn
}

output "validate_input_function_name" {
  description = "Name of the validate input Lambda function"
  value       = aws_lambda_function.validate_input.function_name
}

output "validate_input_function_arn" {
  description = "ARN of the validate input Lambda function"
  value       = aws_lambda_function.validate_input.arn
}

output "clear_staging_function_name" {
  description = "Name of the clear staging Lambda function"
  value       = aws_lambda_function.clear_staging.function_name
}

output "clear_staging_function_arn" {
  description = "ARN of the clear staging Lambda function"
  value       = aws_lambda_function.clear_staging.arn
}

output "check_failures_function_name" {
  description = "Name of the check failures Lambda function"
  value       = aws_lambda_function.check_failures.function_name
}

output "check_failures_function_arn" {
  description = "ARN of the check failures Lambda function"
  value       = aws_lambda_function.check_failures.arn
}

output "catalog_build_function_name" {
  description = "Name of the catalog build Lambda function"
  value       = aws_lambda_function.catalog_build.function_name
}

output "catalog_build_function_arn" {
  description = "ARN of the catalog build Lambda function"
  value       = aws_lambda_function.catalog_build.arn
}

output "dynamodb_load_function_name" {
  description = "Name of the DynamoDB load Lambda function"
  value       = aws_lambda_function.dynamodb_load.function_name
}

output "dynamodb_load_function_arn" {
  description = "ARN of the DynamoDB load Lambda function"
  value       = aws_lambda_function.dynamodb_load.arn
}
