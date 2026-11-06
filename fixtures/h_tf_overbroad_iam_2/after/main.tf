locals {
  resource_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = var.service_name
    }
  )

  compaction_name = "${var.service_name}-${var.environment}-session-compaction"
}

resource "aws_dynamodb_table" "sessions" {
  name         = "${var.service_name}-${var.environment}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = var.session_ttl_attribute
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.resource_tags
}

resource "aws_cloudwatch_event_rule" "session_compaction" {
  name                = local.compaction_name
  description         = "Runs periodic compaction of expired authentication sessions."
  schedule_expression = var.compaction_schedule
  state               = var.compaction_enabled ? "ENABLED" : "DISABLED"

  tags = local.resource_tags
}

resource "aws_cloudwatch_event_target" "session_compaction" {
  rule      = aws_cloudwatch_event_rule.session_compaction.name
  target_id = "session-compactor"
  arn       = var.compaction_cluster_arn
  role_arn  = aws_iam_role.session_compaction_scheduler.arn

  ecs_target {
    task_definition_arn = var.compaction_task_definition_arn
    task_count          = 1
    launch_type         = "FARGATE"
    platform_version    = "LATEST"

    network_configuration {
      assign_public_ip = false
      security_groups  = var.compaction_security_group_ids
      subnets          = var.compaction_subnet_ids
    }
  }

  input = jsonencode({
    containerOverrides = [
      {
        name = var.compaction_container_name
        environment = [
          {
            name  = "SESSION_TABLE_NAME"
            value = aws_dynamodb_table.sessions.name
          },
          {
            name  = "SESSION_TTL_ATTRIBUTE"
            value = var.session_ttl_attribute
          }
        ]
      }
    ]
  })
}
