variable "name" {
  description = "Name prefix for worker resources."
  type        = string
}

variable "account_id" {
  description = "AWS account that owns the scheduler."
  type        = string
  default     = "111111111111"
}

variable "cluster_arn" {
  description = "ARN of the ECS cluster that runs the worker."
  type        = string
}

variable "task_definition_arn" {
  description = "ARN of the worker task definition."
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the worker task role."
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the worker task execution role."
  type        = string
}

variable "additional_worker_role_arns" {
  description = "Extra IAM role ARNs used by containers in the scheduled task."
  type        = list(string)
  default     = ["*"]
}

variable "container_name" {
  description = "Name of the worker container in the task definition."
  type        = string
  default     = "worker"
}

variable "subnet_ids" {
  description = "Subnet IDs used by scheduled worker tasks."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs used by scheduled worker tasks."
  type        = list(string)
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression for polling the queue."
  type        = string
  default     = "rate(5 minutes)"
}

variable "schedule_timezone" {
  description = "IANA time zone used to evaluate the schedule."
  type        = string
  default     = "UTC"
}

variable "max_receive_count" {
  description = "Number of processing attempts before a job moves to the dead-letter queue."
  type        = number
  default     = 5

  validation {
    condition     = var.max_receive_count >= 1
    error_message = "max_receive_count must be at least 1."
  }
}

variable "dlq_message_retention_seconds" {
  description = "Retention period for failed jobs."
  type        = number
  default     = 1209600
}

variable "alarm_topic_arns" {
  description = "SNS topic ARNs notified when failed jobs reach the dead-letter queue."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for created resources."
  type        = map(string)
  default     = {}
}
