data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  queue_name = "${var.service_name}-${var.environment}-orders"
  tags = merge(var.tags, {
    Service     = var.service_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
  legacy_dashboard_namespace = var.legacy_metric_namespace
}

resource "aws_sqs_queue" "order_queue" {
  name                       = local.queue_name
  message_retention_seconds  = var.message_retention_seconds
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true

  tags = local.tags
}
