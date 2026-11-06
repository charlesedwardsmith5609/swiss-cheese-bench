variable "archive_bucket_name" {
  description = "Globally unique name of the invoice archive bucket."
  type        = string

  validation {
    condition = (
      length(var.archive_bucket_name) >= 3 &&
      length(var.archive_bucket_name) <= 63 &&
      can(regex("^[a-z0-9][a-z0-9.-]*[a-z0-9]$", var.archive_bucket_name)) &&
      !strcontains(var.archive_bucket_name, "..")
    )
    error_message = "archive_bucket_name must be a valid S3 bucket name."
  }
}

variable "invoice_prefix" {
  description = "Object key prefix used for generated invoices."
  type        = string
  default     = "invoices/"

  validation {
    condition = (
      length(var.invoice_prefix) > 1 &&
      !startswith(var.invoice_prefix, "/") &&
      endswith(var.invoice_prefix, "/")
    )
    error_message = "invoice_prefix must be a nonempty relative prefix ending in a slash."
  }
}

variable "invoice_exporter_role_name" {
  description = "Name of the existing IAM role used by the invoice exporter."
  type        = string

  validation {
    condition     = length(trimspace(var.invoice_exporter_role_name)) > 0
    error_message = "invoice_exporter_role_name must not be empty."
  }
}

variable "tags" {
  description = "Tags applied to invoice archive resources."
  type        = map(string)
  default     = {}
}
