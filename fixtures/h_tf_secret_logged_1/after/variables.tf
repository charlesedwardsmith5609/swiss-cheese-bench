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

variable "queue_visibility_timeout_seconds" {
  description = "Time an order remains hidden after a consumer receives it."
  type        = number
  default     = 45

  validation {
    condition = (
      var.queue_visibility_timeout_seconds >= 1 &&
      var.queue_visibility_timeout_seconds <= 43200
    )
    error_message = "queue_visibility_timeout_seconds must be between 1 and 43200."
  }
}

variable "fulfillment_connector" {
  description = "Configuration used to deliver completed orders to fulfillment."
  type = object({
    enabled         = optional(bool, false)
    endpoint        = string
    headers         = optional(map(string), {})
    timeout_seconds = optional(number, 5)
  })

  default = {
    enabled  = false
    endpoint = "https://fulfillment.example.invalid/v1/orders"
    headers = {
      Authorization = "Bearer EXAMPLE-NOT-A-REAL-TOKEN-0000"
    }
    timeout_seconds = 5
  }

  validation {
    condition = (
      !var.fulfillment_connector.enabled ||
      can(regex("^https://", var.fulfillment_connector.endpoint))
    )
    error_message = "An enabled fulfillment connector must use an HTTPS endpoint."
  }

  validation {
    condition = (
      var.fulfillment_connector.timeout_seconds >= 1 &&
      var.fulfillment_connector.timeout_seconds <= 30
    )
    error_message = "fulfillment connector timeout_seconds must be between 1 and 30."
  }
}

variable "tags" {
  description = "Additional tags applied to module resources."
  type        = map(string)
  default     = {}
}
