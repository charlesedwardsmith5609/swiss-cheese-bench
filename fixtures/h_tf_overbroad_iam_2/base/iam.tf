data "aws_iam_policy_document" "api_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.service_name}-${var.environment}-api"
  assume_role_policy = data.aws_iam_policy_document.api_assume_role.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "api" {
  statement {
    sid    = "SessionItems"
    effect = "Allow"
    actions = [
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.sessions.arn]
  }

  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/${var.service_name}-${var.environment}-*:*"]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "session-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}
