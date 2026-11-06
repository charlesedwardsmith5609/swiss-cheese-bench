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

variable "archive_transition_days" {
  description = "Days before invoice objects and prior versions transition to STANDARD_IA."
  type        = number
  default     = 90

  validation {
    condition = (
      var.archive_transition_days >= 30 &&
      floor(var.archive_transition_days) == var.archive_transition_days
    )
    error_message = "archive_transition_days must be an integer of at least 30."
  }
}

variable "archive_retention_days" {
  description = "Days before invoice objects and prior versions expire."
  type        = number
  default     = 2555

  validation {
    condition = (
      var.archive_retention_days >= 365 &&
      floor(var.archive_retention_days) == var.archive_retention_days
    )
    error_message = "archive_retention_days must be an integer of at least 365."
  }
}

variable "archive_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN; null uses S3-managed AES-256 encryption."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = var.archive_kms_key_arn == null ? true : can(
      regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/[0-9a-fA-F-]+$", var.archive_kms_key_arn)
    )
    error_message = "archive_kms_key_arn must be null or a KMS key ARN."
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
