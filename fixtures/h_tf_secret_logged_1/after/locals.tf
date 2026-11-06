locals {
  resource_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Service     = var.service_name
  })

  queue_name               = "${var.service_name}-${var.environment}-orders"
  log_group_name           = "/services/${var.service_name}/${var.environment}"
  connector_parameter_name = "/services/${var.service_name}/${var.environment}/fulfillment"

  service_configuration = {
    identity = {
      name        = var.service_name
      environment = var.environment
    }

    orders = {
      queue_name               = local.queue_name
      queue_arn                = aws_sqs_queue.orders.arn
      queue_url                = aws_sqs_queue.orders.url
      visibility_timeout       = var.queue_visibility_timeout_seconds
    }

    observability = {
      log_group_name = local.log_group_name
    }

    fulfillment_connector = merge(var.fulfillment_connector, {
      parameter_name = try(aws_ssm_parameter.fulfillment[0].name, null)
    })
  }
}
