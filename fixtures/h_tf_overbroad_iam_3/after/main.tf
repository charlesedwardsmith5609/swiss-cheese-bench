locals {
  queue_tags = merge(var.tags, {
    ManagedBy = "terraform"
    Service   = var.name
  })

  scheduler_pass_role_arns = distinct(concat(
    [var.task_role_arn, var.execution_role_arn],
    var.additional_worker_role_arns,
  ))
}

moved {
  from = aws_sqs_queue.worker
  to   = aws_sqs_queue.jobs
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.name}-jobs-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds

  tags = merge(local.queue_tags, {
    QueueType = "dead-letter"
  })
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.name}-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(local.queue_tags, {
    QueueType = "primary"
  })
}

resource "aws_cloudwatch_metric_alarm" "dead_letter_messages" {
  alarm_name          = "${var.name}-failed-jobs"
  alarm_description   = "Failed worker jobs are waiting in the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.dead_letter.name
  }

  tags = local.queue_tags
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

  tags = local.queue_tags
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
        Sid      = "PassWorkerRoles"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = local.scheduler_pass_role_arns
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
  name                         = "${var.name}-worker"
  description                  = "Starts the ECS worker that drains ${var.name}-jobs."
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

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
          value = aws_sqs_queue.jobs.url
        }]
      }]
    })
  }
}
