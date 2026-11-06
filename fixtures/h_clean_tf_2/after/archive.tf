resource "aws_s3_bucket" "invoice_archive" {
  bucket = var.archive_bucket_name
  tags   = local.archive_tags
}

resource "aws_s3_bucket_ownership_controls" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  rule {
    bucket_key_enabled = local.archive_uses_kms

    apply_server_side_encryption_by_default {
      kms_master_key_id = var.archive_kms_key_arn
      sse_algorithm     = local.archive_uses_kms ? "aws:kms" : "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  depends_on = [aws_s3_bucket_versioning.invoice_archive]

  rule {
    id     = "invoice-retention"
    status = "Enabled"

    filter {
      prefix = local.archive_object_prefix
    }

    transition {
      days          = var.archive_transition_days
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = var.archive_retention_days
    }

    noncurrent_version_transition {
      noncurrent_days = var.archive_transition_days
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = var.archive_retention_days
    }
  }

  lifecycle {
    precondition {
      condition     = var.archive_transition_days < var.archive_retention_days
      error_message = "archive_transition_days must be less than archive_retention_days."
    }
  }
}

data "aws_iam_policy_document" "invoice_archive_transport" {
  statement {
    sid    = "DenyUnencryptedTransport"
    effect = "Deny"

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.invoice_archive.arn,
      "${aws_s3_bucket.invoice_archive.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "invoice_archive_transport" {
  bucket = aws_s3_bucket.invoice_archive.id
  policy = data.aws_iam_policy_document.invoice_archive_transport.json
}

data "aws_iam_policy_document" "invoice_archive_writer" {
  statement {
    sid = "WriteInvoiceObjects"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.invoice_archive.arn}/${local.archive_object_prefix}*",
    ]
  }

  statement {
    sid = "ReadArchiveMetadata"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [aws_s3_bucket.invoice_archive.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.archive_object_prefix}*"]
    }
  }

  dynamic "statement" {
    for_each = local.archive_uses_kms ? [var.archive_kms_key_arn] : []

    content {
      sid = "EncryptInvoiceObjects"

      actions = [
        "kms:DescribeKey",
        "kms:Encrypt",
        "kms:GenerateDataKey",
      ]

      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "invoice_archive_writer" {
  name   = "invoice-archive-writer"
  role   = var.invoice_exporter_role_name
  policy = data.aws_iam_policy_document.invoice_archive_writer.json
}
