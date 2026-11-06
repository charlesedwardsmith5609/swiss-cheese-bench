locals {
  invoice_object_prefix = var.invoice_prefix

  archive_tags = merge(
    var.tags,
    {
      Component = "billing"
      DataClass = "financial"
      ManagedBy = "terraform"
    },
  )
}
