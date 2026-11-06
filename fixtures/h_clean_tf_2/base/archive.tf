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
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "invoice_archive_writer" {
  statement {
    sid = "WriteInvoiceObjects"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.invoice_archive.arn}/${local.invoice_object_prefix}*",
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
      values   = ["${local.invoice_object_prefix}*"]
    }
  }
}

resource "aws_iam_role_policy" "invoice_archive_writer" {
  name   = "invoice-archive-writer"
  role   = var.invoice_exporter_role_name
  policy = data.aws_iam_policy_document.invoice_archive_writer.json
}
