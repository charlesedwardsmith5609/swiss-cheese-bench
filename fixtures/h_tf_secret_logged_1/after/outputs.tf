output "service_configuration" {
  description = "Runtime configuration consumed by service deployment tooling."
  value       = local.service_configuration
}

output "orders_queue_arn" {
  description = "ARN of the queue that receives order events."
  value       = aws_sqs_queue.orders.arn
}

output "orders_queue_url" {
  description = "URL of the queue that receives order events."
  value       = aws_sqs_queue.orders.url
}

output "fulfillment_connector_parameter_arn" {
  description = "ARN of the fulfillment connector parameter when enabled."
  value       = try(aws_ssm_parameter.fulfillment[0].arn, null)
}
