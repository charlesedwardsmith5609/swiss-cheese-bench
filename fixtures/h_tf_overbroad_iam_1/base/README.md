# Billing invoice scheduler

This module provisions an S3 bucket, a Step Functions workflow, and an EventBridge rule for nightly invoice generation.

## Usage

```hcl
module "invoice_scheduler" {
  source = "./modules/invoice-scheduler"

  billing_service     = "ledger"
  invoice_bucket_name = "ledger-invoices-111111111111"
  invoice_schedule    = "cron(0 2 * * ? *)"

  tags = {
    Environment = "production"
    Team        = "billing"
  }
}
```

The schedule is evaluated by EventBridge in UTC. Generated invoice objects remain in the versioned bucket until removed by the caller's data-retention process.

## Outputs

- `invoice_bucket_arn` — invoice storage bucket ARN
- `workflow_arn` — invoice generation workflow ARN
- `trigger_arn` — nightly EventBridge rule ARN
