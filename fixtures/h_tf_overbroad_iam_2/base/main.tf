locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      Service     = var.service_name
      ManagedBy   = "terraform"
    }
  )
}

resource "aws_dynamodb_table" "sessions" {
  name         = "${var.service_name}-${var.environment}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = var.session_ttl_attribute
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.common_tags
}
