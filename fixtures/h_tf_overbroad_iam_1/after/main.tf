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
  schedule_name = "${var.billing_service}-nightly-invoices"
  resource_tags = merge(var.tags, {
    Component = "billing-invoices"
    ManagedBy = "terraform"
  })
}

moved {
  from = aws_s3_bucket.invoice_archive
  to   = aws_s3_bucket.invoice_store
}

resource "aws_s3_bucket" "invoice_store" {
  bucket = var.invoice_bucket_name
  tags   = local.resource_tags
}

resource "aws_s3_bucket_versioning" "invoice_archive" {
  bucket = aws_s3_bucket.invoice_store.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "invoice_store" {
  bucket = aws_s3_bucket.invoice_store.id

  rule {
    id     = "expire-invoice-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = var.invoice_retention_days
    }
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
  tags               = local.resource_tags
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

  tags = local.resource_tags
}

data "aws_iam_policy_document" "trigger_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "trigger" {
  name               = "${var.billing_service}-schedule-trigger"
  assume_role_policy = data.aws_iam_policy_document.trigger_assume.json
  tags               = local.resource_tags
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

resource "aws_scheduler_schedule_group" "billing" {
  name = "${var.billing_service}-billing"
  tags = local.resource_tags
}

resource "aws_scheduler_schedule" "nightly_invoices" {
  name                         = local.schedule_name
  group_name                   = aws_scheduler_schedule_group.billing.name
  description                  = "Starts nightly invoice generation"
  schedule_expression          = var.invoice_schedule
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.invoice_generation.arn
    role_arn = aws_iam_role.trigger.arn
    input = jsonencode({
      source = "nightly-schedule"
    })

    retry_policy {
      maximum_event_age_in_seconds = var.maximum_event_age_seconds
      maximum_retry_attempts       = var.maximum_retry_attempts
    }
  }
}
