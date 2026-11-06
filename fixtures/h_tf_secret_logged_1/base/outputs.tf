output "service_summary" {
  description = "Stable identifiers for the order-management service."
  value       = local.service_summary
}

output "orders_queue_arn" {
  description = "ARN of the queue that receives order events."
  value       = aws_sqs_queue.orders.arn
}

output "orders_queue_url" {
  description = "URL of the queue that receives order events."
  value       = aws_sqs_queue.orders.url
}
