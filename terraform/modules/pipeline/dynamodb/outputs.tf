output "table_name" {
  description = "Name of the DynamoDB serving table"
  value       = aws_dynamodb_table.serving.name
}

output "table_arn" {
  description = "ARN of the DynamoDB serving table"
  value       = aws_dynamodb_table.serving.arn
}
