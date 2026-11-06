# Scheduled queue worker

This module creates an SQS job queue and an EventBridge Scheduler schedule that starts an ECS worker task.

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

  tags = {
    Environment = "production"
  }
}
```

The task receives the queue URL in the `JOB_QUEUE_URL` environment variable. The task role is responsible for queue-level permissions used by the worker.
