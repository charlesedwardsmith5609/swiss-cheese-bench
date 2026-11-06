data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  queue_name = "${var.service_name}-${var.environment}-orders"
  dlq_name   = "${local.queue_name}-dlq"
  tags = merge(var.tags, {
    Service     = var.service_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Account     = data.aws_caller_identity.current.account_id
  })
  archive_prefix = var.archive_key_prefix == "" ? "orders/" : var.archive_key_prefix
}

moved {
  from = aws_sqs_queue.order_queue
  to   = aws_sqs_queue.orders
}

resource "aws_sqs_queue" "orders_dlq" {
  name                      = local.dlq_name
  message_retention_seconds = var.message_retention_seconds
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}

resource "aws_sqs_queue" "orders" {
  name                       = local.queue_name
  message_retention_seconds  = var.message_retention_seconds
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 5
  })

  tags = local.tags
}
