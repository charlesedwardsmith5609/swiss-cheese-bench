locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Service     = var.service_name
  })

  queue_name     = "${var.service_name}-${var.environment}-orders"
  log_group_name = "/services/${var.service_name}/${var.environment}"

  service_summary = {
    name           = var.service_name
    environment    = var.environment
    queue_name     = local.queue_name
    log_group_name = local.log_group_name
  }
}
