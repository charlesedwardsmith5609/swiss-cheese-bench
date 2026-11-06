# Billing invoice scheduler

This module provisions versioned S3 storage, a Step Functions workflow, and an EventBridge Scheduler schedule for nightly invoice generation.

## Usage

```hcl
module "invoice_scheduler" {
  source = "./modules/invoice-scheduler"

  billing_service       = "ledger"
  invoice_bucket_name   = "ledger-invoices-111111111111"
  invoice_schedule      = "cron(0 2 * * ? *)"
  schedule_timezone     = "America/Los_Angeles"
  invoice_retention_days = 2555

  maximum_event_age_seconds = 3600
  maximum_retry_attempts     = 2

  tags = {
    Environment = "production"
    Team        = "billing"
  }
}
```

EventBridge Scheduler evaluates the expression in `schedule_timezone` and retries transient workflow invocation failures according to the configured retry settings. Generated invoice artifacts expire after `invoice_retention_days`; bucket versioning remains enabled.

The internal bucket resource was renamed without changing its state address, so existing module installations can upgrade without recreating invoice storage.

## Outputs

- `invoice_bucket_arn` — invoice storage bucket ARN
- `workflow_arn` — invoice generation workflow ARN
- `trigger_arn` — nightly EventBridge Scheduler schedule ARN
