# Scheduled queue worker

This module creates an SQS job queue, a dead-letter queue, and an EventBridge Scheduler schedule that starts an ECS worker task. A CloudWatch alarm reports jobs that exhaust their configured processing attempts.

## Example

```hcl
module "queue_worker" {
  source = "./modules/queue-worker"

  name                = "thumbnailer"
  account_id          = "111111111111"
  cluster_arn         = aws_ecs_cluster.workers.arn
  task_definition_arn = aws_ecs_task_definition.thumbnailer.arn
  task_role_arn        = aws_iam_role.thumbnailer_task.arn
  execution_role_arn   = aws_iam_role.ecs_execution.arn
  subnet_ids           = module.vpc.private_subnet_ids
  security_group_ids   = [aws_security_group.worker.id]

  schedule_expression = "cron(0/10 * * * ? *)"
  schedule_timezone   = "America/Los_Angeles"
  max_receive_count   = 4
  alarm_topic_arns    = [aws_sns_topic.operations.arn]

  additional_worker_role_arns = [
    aws_iam_role.telemetry_sidecar.arn,
  ]

  tags = {
    Environment = "production"
  }
}
```

The worker container receives the primary queue URL in the `JOB_QUEUE_URL` environment variable. Messages that exceed `max_receive_count` are moved to the dead-letter queue and retained for 14 days by default.

The task role remains responsible for queue-level permissions used by the worker. List any roles used by sidecar containers in `additional_worker_role_arns` so scheduled tasks can start with the complete task definition.

## Outputs

- `queue_url` and `queue_arn` identify the primary job queue.
- `dead_letter_queue_url` and `dead_letter_queue_arn` identify the failed-job queue.
