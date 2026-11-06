variable "billing_service" {
  description = "Name used to identify the billing service resources."
  type        = string
}

variable "invoice_bucket_name" {
  description = "Globally unique bucket name for generated invoice artifacts."
  type        = string
}

variable "invoice_schedule" {
  description = "EventBridge Scheduler cron or rate expression for invoice generation."
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "schedule_timezone" {
  description = "IANA timezone used to evaluate the invoice schedule."
  type        = string
  default     = "UTC"
}

variable "invoice_retention_days" {
  description = "Number of days generated invoice artifacts are retained."
  type        = number
  default     = 2555

  validation {
    condition     = var.invoice_retention_days > 0
    error_message = "Invoice retention must be greater than zero days."
  }
}

variable "maximum_event_age_seconds" {
  description = "Maximum age of a failed scheduled invocation before it is discarded."
  type        = number
  default     = 3600

  validation {
    condition     = var.maximum_event_age_seconds >= 60 && var.maximum_event_age_seconds <= 86400
    error_message = "Maximum event age must be between 60 and 86400 seconds."
  }
}

variable "maximum_retry_attempts" {
  description = "Number of times Scheduler retries a failed workflow invocation."
  type        = number
  default     = 2

  validation {
    condition     = var.maximum_retry_attempts >= 0 && var.maximum_retry_attempts <= 185
    error_message = "Maximum retry attempts must be between 0 and 185."
  }
}

variable "tags" {
  description = "Additional tags applied to module resources."
  type        = map(string)
  default     = {}
}
