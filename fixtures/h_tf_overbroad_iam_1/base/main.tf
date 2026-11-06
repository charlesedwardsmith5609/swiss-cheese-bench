terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  trigger_name = "${var.billing_service}-nightly-invoices"
  common_tags = merge(var.tags, {
    Component = "billing-invoices"
    ManagedBy = "terraform"
  })
}

resource "aws_s3_bucket" "invoice_archive" {
  bucket = var.invoice_bucket_name
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "workflow_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "workflow" {
  name               = "${var.billing_service}-invoice-workflow"
  assume_role_policy = data.aws_iam_policy_document.workflow_assume.json
  tags               = local.common_tags
}

resource "aws_sfn_state_machine" "invoice_generation" {
  name     = "${var.billing_service}-invoice-generation"
  role_arn = aws_iam_role.workflow.arn

  definition = jsonencode({
    Comment = "Coordinates nightly invoice generation"
    StartAt = "PrepareInvoiceBatch"
    States = {
      PrepareInvoiceBatch = {
        Type = "Pass"
        Result = {
          bucket = var.invoice_bucket_name
        }
        End = true
      }
    }
  })

  tags = local.common_tags
}

data "aws_iam_policy_document" "trigger_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        "arn:${data.aws_partition.current.partition}:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${local.trigger_name}"
      ]
    }
  }
}

resource "aws_iam_role" "trigger" {
  name               = "${var.billing_service}-event-trigger"
  assume_role_policy = data.aws_iam_policy_document.trigger_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "start_workflow" {
  statement {
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.invoice_generation.arn]
  }
}

resource "aws_iam_role_policy" "start_workflow" {
  name   = "start-invoice-workflow"
  role   = aws_iam_role.trigger.id
  policy = data.aws_iam_policy_document.start_workflow.json
}

resource "aws_cloudwatch_event_rule" "nightly_invoices" {
  name                = local.trigger_name
  description         = "Starts nightly invoice generation"
  schedule_expression = var.invoice_schedule
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_target" "invoice_workflow" {
  rule     = aws_cloudwatch_event_rule.nightly_invoices.name
  arn      = aws_sfn_state_machine.invoice_generation.arn
  role_arn = aws_iam_role.trigger.arn

  input = jsonencode({
    source = "nightly-schedule"
  })
}
