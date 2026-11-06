output "order_queue_arn" {
  description = "ARN of the order queue."
  value       = aws_sqs_queue.orders.arn
}

output "order_queue_url" {
  description = "URL of the order queue."
  value       = aws_sqs_queue.orders.url
}

output "worker_runtime" {
  description = "Non-secret settings the order worker reads at startup."
  value = {
    queue_url      = aws_sqs_queue.orders.url
    archive_bucket = aws_s3_bucket.fulfillment_archive.bucket
    archive_prefix = local.archive_prefix
    status_bus     = aws_cloudwatch_event_bus.order_status.name
    region         = data.aws_region.current.name
  }
}
