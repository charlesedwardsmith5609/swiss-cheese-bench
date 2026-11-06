variable "billing_service" {
  description = "Name used to identify the billing service resources."
  type        = string
}

variable "invoice_bucket_name" {
  description = "Globally unique bucket name for generated invoice artifacts."
  type        = string
}

variable "invoice_schedule" {
  description = "EventBridge cron or rate expression for invoice generation."
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "tags" {
  description = "Additional tags applied to module resources."
  type        = map(string)
  default     = {}
}
