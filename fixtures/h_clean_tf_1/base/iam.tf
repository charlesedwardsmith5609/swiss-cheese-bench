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

    resources = [aws_sqs_queue.order_queue.arn]

    principals {
      type        = "AWS"
      identifiers = [var.worker_role_arn]
    }
  }
}

resource "aws_sqs_queue_policy" "orders" {
  queue_url = aws_sqs_queue.order_queue.id
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

    resources = [aws_sqs_queue.order_queue.arn]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.service_name}-${var.environment}-orders"
  role   = element(split("/", var.worker_role_arn), length(split("/", var.worker_role_arn)) - 1)
  policy = data.aws_iam_policy_document.worker.json
}
