variable "service_name" {
  description = "Name of the order-management service."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]+$", var.service_name))
    error_message = "service_name must use lowercase letters, digits, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "visibility_timeout_seconds" {
  description = "Time an order remains hidden after a consumer receives it."
  type        = number
  default     = 45

  validation {
    condition     = var.visibility_timeout_seconds >= 1 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds must be between 1 and 43200."
  }
}

variable "tags" {
  description = "Additional tags applied to module resources."
  type        = map(string)
  default     = {}
}
