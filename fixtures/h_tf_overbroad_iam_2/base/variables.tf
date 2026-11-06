variable "service_name" {
  description = "Name of the authentication service."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "session_ttl_attribute" {
  description = "DynamoDB attribute containing the session expiry epoch."
  type        = string
  default     = "expires_at"
}

variable "tags" {
  description = "Additional tags applied to managed resources."
  type        = map(string)
  default     = {}
}
