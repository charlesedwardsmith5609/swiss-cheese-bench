resource "aws_sqs_queue" "orders" {
  name                       = local.queue_name
  visibility_timeout_seconds = var.queue_visibility_timeout_seconds
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true

  tags = local.resource_tags
}

resource "aws_cloudwatch_log_group" "service" {
  name              = local.log_group_name
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = local.resource_tags
}

resource "aws_ssm_parameter" "fulfillment" {
  count = var.fulfillment_connector.enabled ? 1 : 0

  name        = local.connector_parameter_name
  description = "Fulfillment connector configuration for ${var.service_name}."
  type        = "SecureString"
  value = jsonencode({
    endpoint        = var.fulfillment_connector.endpoint
    headers         = var.fulfillment_connector.headers
    timeout_seconds = var.fulfillment_connector.timeout_seconds
  })

  tags = local.resource_tags
}
