output "session_table_name" {
  description = "Name of the authentication session table."
  value       = aws_dynamodb_table.sessions.name
}

output "api_role_arn" {
  description = "ARN of the role used by the authentication API."
  value       = aws_iam_role.api.arn
}
