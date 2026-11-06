output "session_table_name" {
  description = "Name of the authentication session table."
  value       = aws_dynamodb_table.sessions.name
}

output "api_role_arn" {
  description = "ARN of the role used by the authentication API."
  value       = aws_iam_role.api.arn
}

output "compaction_schedule_arn" {
  description = "ARN of the session compaction schedule."
  value       = aws_cloudwatch_event_rule.session_compaction.arn
}

output "compaction_scheduler_role_arn" {
  description = "ARN of the role used to start compaction tasks."
  value       = aws_iam_role.session_compaction_scheduler.arn
}
