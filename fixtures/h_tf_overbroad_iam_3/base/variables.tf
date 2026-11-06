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

variable "tags" {
  description = "Additional tags for created resources."
  type        = map(string)
  default     = {}
}
