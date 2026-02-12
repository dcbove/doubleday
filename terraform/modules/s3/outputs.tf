output "lakehouse_bucket_name" {
  description = "Name of the lakehouse S3 bucket"
  value       = aws_s3_bucket.lakehouse.id
}

output "lakehouse_bucket_arn" {
  description = "ARN of the lakehouse S3 bucket"
  value       = aws_s3_bucket.lakehouse.arn
}
