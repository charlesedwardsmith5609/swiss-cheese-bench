output "archive_bucket_name" {
  description = "Name of the invoice archive bucket."
  value       = aws_s3_bucket.invoice_archive.id
}

output "invoice_object_prefix" {
  description = "Object key prefix reserved for generated invoices."
  value       = local.invoice_object_prefix
}
