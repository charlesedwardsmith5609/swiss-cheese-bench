# Order-management infrastructure

This module provisions the queue and log group used by an order-management service.

## Usage

```hcl
module "orders" {
  source = "./modules/order-management"

  service_name = "order-api"
  environment  = "staging"

  visibility_timeout_seconds = 60

  tags = {
    Team = "commerce"
  }
}
```

## Inputs

- `service_name`: lowercase service identifier.
- `environment`: `development`, `staging`, or `production`.
- `visibility_timeout_seconds`: queue visibility timeout; defaults to 45 seconds.
- `tags`: additional resource tags.

## Outputs

- `service_summary`: stable service identifiers.
- `orders_queue_arn`: ARN of the orders queue.
- `orders_queue_url`: URL of the orders queue.
