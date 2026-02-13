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
