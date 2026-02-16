output "state_machine_arn" {
  description = "ARN of the pipeline Step Function"
  value       = aws_sfn_state_machine.pipeline.arn
}

output "state_machine_name" {
  description = "Name of the pipeline Step Function"
  value       = aws_sfn_state_machine.pipeline.name
}
