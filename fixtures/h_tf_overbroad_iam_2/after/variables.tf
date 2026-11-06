variable "service_name" {
  description = "Name of the authentication service."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "session_ttl_attribute" {
  description = "DynamoDB attribute containing the session expiry epoch."
  type        = string
  default     = "expires_at"
}

variable "compaction_enabled" {
  description = "Whether scheduled session compaction is enabled."
  type        = bool
  default     = true
}

variable "compaction_schedule" {
  description = "EventBridge schedule expression for session compaction."
  type        = string
  default     = "rate(15 minutes)"
}

variable "compaction_cluster_arn" {
  description = "ARN of the ECS cluster that runs the compaction task."
  type        = string
}

variable "compaction_task_definition_arn" {
  description = "ARN of the ECS task definition used for compaction."
  type        = string
}

variable "compaction_task_role_arn" {
  description = "ARN of the application role assigned to the compaction task."
  type        = string
}

variable "compaction_execution_role_arn" {
  description = "ARN of the ECS execution role assigned to the compaction task."
  type        = string
}

variable "compaction_container_name" {
  description = "Name of the compaction container in the task definition."
  type        = string
  default     = "session-compactor"
}

variable "compaction_subnet_ids" {
  description = "Private subnet IDs used by the compaction task."
  type        = list(string)
}

variable "compaction_security_group_ids" {
  description = "Security group IDs used by the compaction task."
  type        = list(string)
}

variable "tags" {
  description = "Additional tags applied to managed resources."
  type        = map(string)
  default     = {}
}
