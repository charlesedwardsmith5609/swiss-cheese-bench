resource "aws_sqs_queue" "orders" {
  name                       = local.queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "service" {
  name              = local.log_group_name
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = local.common_tags
}
