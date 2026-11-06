locals {
  archive_object_prefix = var.invoice_prefix
  archive_uses_kms      = var.archive_kms_key_arn != null

  archive_tags = merge(
    var.tags,
    {
      Component = "billing"
      DataClass = "financial"
      ManagedBy = "terraform"
    },
  )
}
