# Sandbox inputs for terraform plan -var-file=dev.tfvars. Not auto-loaded.

service_name        = "order-mgmt"
environment         = "dev"
archive_bucket_name = "order-mgmt-dev-fulfillment-example"
archive_key_prefix  = ""
worker_role_arn     = "arn:aws:iam::123456789012:role/order-mgmt-dev-worker"
alarm_topic_arns = [
  "arn:aws:sns:us-east-1:123456789012:order-mgmt-dev-ops",
]
message_retention_seconds  = 345600
visibility_timeout_seconds = 90
tags = {
  Owner      = "orders-platform"
  CostCenter = "CC-1044"
}
