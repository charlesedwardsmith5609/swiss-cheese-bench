resource "aws_cloudwatch_event_bus" "order_status" {
  name = "${var.service_name}-${var.environment}-order-status"
  tags = local.tags
}

resource "aws_s3_bucket" "fulfillment_archive" {
  bucket = var.archive_bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_public_access_block" "fulfillment_archive" {
  bucket                  = aws_s3_bucket.fulfillment_archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "fulfillment_archive" {
  bucket = aws_s3_bucket.fulfillment_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "fulfillment_archive" {
  bucket = aws_s3_bucket.fulfillment_archive.id

  rule {
    id     = "abort-stale-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "orders_dlq" {
  alarm_name          = "${local.dlq_name}-not-empty"
  alarm_description   = "Orders that failed processing are waiting on the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 60
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arns

  dimensions = {
    QueueName = aws_sqs_queue.orders_dlq.name
  }

  tags = local.tags
}
