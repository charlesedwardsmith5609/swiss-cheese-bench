data "aws_iam_policy_document" "orders_queue" {
  statement {
    sid    = "WorkerConsumes"
    effect = "Allow"

    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]

    resources = [aws_sqs_queue.orders.arn]

    principals {
      type        = "AWS"
      identifiers = [var.worker_role_arn]
    }
  }

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.orders.arn]

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

resource "aws_sqs_queue_policy" "orders" {
  queue_url = aws_sqs_queue.orders.id
  policy    = data.aws_iam_policy_document.orders_queue.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid    = "ConsumeOrders"
    effect = "Allow"

    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]

    resources = [aws_sqs_queue.orders.arn]
  }

  statement {
    sid       = "PublishOrderStatus"
    effect    = "Allow"
    actions   = ["events:PutEvents"]
    resources = [aws_cloudwatch_event_bus.order_status.arn]
  }

  statement {
    sid    = "WriteFulfillmentArchive"
    effect = "Allow"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:PutObject",
    ]

    resources = ["${aws_s3_bucket.fulfillment_archive.arn}/${local.archive_prefix}*"]
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.service_name}-${var.environment}-orders"
  role   = element(split("/", var.worker_role_arn), length(split("/", var.worker_role_arn)) - 1)
  policy = data.aws_iam_policy_document.worker.json
}
