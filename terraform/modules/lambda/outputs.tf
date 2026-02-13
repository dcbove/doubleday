output "silver_load_function_name" {
  description = "Name of the silver load Lambda function"
  value       = aws_lambda_function.silver_load.function_name
}

output "silver_load_function_arn" {
  description = "ARN of the silver load Lambda function"
  value       = aws_lambda_function.silver_load.arn
}
