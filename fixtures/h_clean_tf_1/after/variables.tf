variable "service_name" {
  description = "Short name used in order-management resource names."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.service_name))
    error_message = "service_name must be 3-21 characters, start with a letter, and use only lowercase letters, digits, and hyphens."
  }
}

variable "environment" {
  description = "Deployment stage."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "tags" {
  description = "Extra tags merged onto every resource."
  type        = map(string)
  default     = {}
}

variable "message_retention_seconds" {
  description = "Retention for the primary order queue."
  type        = number
  default     = 345600

  validation {
    condition     = var.message_retention_seconds >= 60 && var.message_retention_seconds <= 1209600
    error_message = "message_retention_seconds must be between 60 and 1209600."
  }
}

variable "visibility_timeout_seconds" {
  description = "How long a worker may hold an order message."
  type        = number
  default     = 90

  validation {
    condition     = var.visibility_timeout_seconds >= 30 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds must be between 30 and 43200."
  }
}

variable "worker_role_arn" {
  description = "IAM role that processes orders."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:role/.+", var.worker_role_arn))
    error_message = "worker_role_arn must be an IAM role ARN."
  }
}

variable "archive_bucket_name" {
  description = "Globally unique name of the fulfillment archive bucket."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.archive_bucket_name))
    error_message = "archive_bucket_name must be a valid S3 bucket name."
  }
}

variable "archive_key_prefix" {
  description = "Object key prefix for fulfillment archives. Leave empty to use the module default."
  type        = string
  default     = ""

  validation {
    condition     = var.archive_key_prefix == "" || can(regex("^[a-z0-9][a-z0-9-]{0,30}/$", var.archive_key_prefix))
    error_message = "archive_key_prefix must be empty or a short lowercase prefix ending in a slash."
  }
}

variable "alarm_topic_arns" {
  description = "SNS topics notified when a dead-lettered order is waiting."
  type        = list(string)

  validation {
    condition = length(var.alarm_topic_arns) > 0 && alltrue([
      for arn in var.alarm_topic_arns : can(regex("^arn:aws[a-z-]*:sns:[a-z0-9-]+:[0-9]{12}:.+$", arn))
    ])
    error_message = "Provide at least one SNS topic ARN."
  }
}
