output "archive_bucket_name" {
  description = "Name of the invoice archive bucket."
  value       = aws_s3_bucket.invoice_archive.id
}

output "archive_bucket_arn" {
  description = "ARN of the invoice archive bucket."
  value       = aws_s3_bucket.invoice_archive.arn
}

output "invoice_object_prefix" {
  description = "Object key prefix reserved for generated invoices."
  value       = local.archive_object_prefix
}

output "archive_encryption_type" {
  description = "Server-side encryption mode configured for invoice objects."
  value       = local.archive_uses_kms ? "aws:kms" : "AES256"
}
