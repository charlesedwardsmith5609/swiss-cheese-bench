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
  tags               = local.resource_tags
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
    sid     = "WriteLogs"
    effect  = "Allow"
    actions = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [
      "arn:aws:logs:*:*:log-group:/aws/lambda/${var.service_name}-${var.environment}-*:*",
    ]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "session-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

data "aws_iam_policy_document" "eventbridge_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "session_compaction_scheduler" {
  name               = "${local.compaction_name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume_role.json
  tags               = local.resource_tags
}

data "aws_iam_policy_document" "session_compaction_scheduler" {
  statement {
    sid       = "RunCompactionTask"
    effect    = "Allow"
    actions   = ["ecs:RunTask"]
    resources = [var.compaction_task_definition_arn]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.compaction_cluster_arn]
    }
  }

  statement {
    sid     = "PassCompactionRoles"
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "session_compaction_scheduler" {
  name   = "run-session-compaction"
  role   = aws_iam_role.session_compaction_scheduler.id
  policy = data.aws_iam_policy_document.session_compaction_scheduler.json
}
