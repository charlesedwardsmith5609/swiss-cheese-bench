output "invoice_bucket_arn" {
  description = "ARN of the bucket containing generated invoices."
  value       = aws_s3_bucket.invoice_archive.arn
}

output "workflow_arn" {
  description = "ARN of the invoice generation state machine."
  value       = aws_sfn_state_machine.invoice_generation.arn
}

output "trigger_arn" {
  description = "ARN of the nightly EventBridge rule."
  value       = aws_cloudwatch_event_rule.nightly_invoices.arn
}
