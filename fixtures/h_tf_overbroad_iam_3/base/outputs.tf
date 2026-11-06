output "queue_url" {
  description = "URL of the worker job queue."
  value       = aws_sqs_queue.worker.url
}

output "queue_arn" {
  description = "ARN of the worker job queue."
  value       = aws_sqs_queue.worker.arn
}
