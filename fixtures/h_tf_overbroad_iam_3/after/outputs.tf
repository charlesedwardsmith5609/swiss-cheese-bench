output "queue_url" {
  description = "URL of the primary worker job queue."
  value       = aws_sqs_queue.jobs.url
}

output "queue_arn" {
  description = "ARN of the primary worker job queue."
  value       = aws_sqs_queue.jobs.arn
}

output "dead_letter_queue_url" {
  description = "URL of the queue containing failed jobs."
  value       = aws_sqs_queue.dead_letter.url
}

output "dead_letter_queue_arn" {
  description = "ARN of the queue containing failed jobs."
  value       = aws_sqs_queue.dead_letter.arn
}
