# Order-management infrastructure

This module provisions the queue, log group, and optional fulfillment connector used by an order-management service.

## Usage

```hcl
module "orders" {
  source = "./modules/order-management"

  service_name = "order-api"
  environment  = "staging"

  queue_visibility_timeout_seconds = 60

  fulfillment_connector = {
    enabled  = true
    endpoint = "https://fulfillment.example.invalid/v1/orders"
    headers = {
      Authorization = "Bearer EXAMPLE-NOT-A-REAL-TOKEN-0000"
      X-Client       = "order-api"
    }
    timeout_seconds = 8
  }

  tags = {
    Team = "commerce"
  }
}
```

## Fulfillment connector

When enabled, the module stores the connector endpoint, headers, and request timeout in an encrypted Systems Manager parameter. The service deployment role should receive read access to the parameter ARN exported by the module.

Keeping connector settings in one parameter allows the service to load a consistent configuration during startup and avoids separate updates for each header.

## Inputs

- `service_name`: lowercase service identifier.
- `environment`: `development`, `staging`, or `production`.
- `queue_visibility_timeout_seconds`: queue visibility timeout; defaults to 45 seconds.
- `fulfillment_connector`: optional endpoint, headers, and timeout for completed-order delivery.
- `tags`: additional resource tags.

## Outputs

- `service_configuration`: consolidated runtime settings for deployment tooling.
- `orders_queue_arn`: ARN of the orders queue.
- `orders_queue_url`: URL of the orders queue.
- `fulfillment_connector_parameter_arn`: ARN of the encrypted connector parameter when enabled.
