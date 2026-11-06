locals {
  common_tags = merge(var.tags, {
    ManagedBy = "terraform"
    Service   = var.name
  })
}

resource "aws_sqs_queue" "worker" {
  name                       = "${var.name}-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600

  tags = local.common_tags
}

resource "aws_iam_role" "scheduler" {
  name = "${var.name}-worker-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "scheduler.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = var.account_id
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "scheduler" {
  name = "run-worker-task"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "RunWorkerTask"
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = var.task_definition_arn
        Condition = {
          ArnEquals = {
            "ecs:cluster" = var.cluster_arn
          }
        }
      },
      {
        Sid    = "PassWorkerRoles"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          var.task_role_arn,
          var.execution_role_arn,
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      },
    ]
  })
}

resource "aws_scheduler_schedule" "worker" {
  name                = "${var.name}-worker"
  schedule_expression = var.schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = var.task_definition_arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        subnets          = var.subnet_ids
        security_groups  = var.security_group_ids
        assign_public_ip = false
      }
    }

    input = jsonencode({
      containerOverrides = [{
        name = var.container_name
        environment = [{
          name  = "JOB_QUEUE_URL"
          value = aws_sqs_queue.worker.url
        }]
      }]
    })
  }
}
