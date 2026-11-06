output "order_queue_arn" {
  description = "ARN of the order queue."
  value       = aws_sqs_queue.order_queue.arn
}

output "order_queue_url" {
  description = "URL of the order queue."
  value       = aws_sqs_queue.order_queue.url
}

output "legacy_metric_namespace" {
  description = "Namespace of the retired order dashboard."
  value       = local.legacy_dashboard_namespace
}
