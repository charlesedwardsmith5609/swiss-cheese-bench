"""Partner webhook receiver.

``accept`` validates a decoded JSON body and records an idempotent receipt.
``verify`` checks the HMAC of the raw bytes before the body is decoded.
"""

from hooks.accept import accept
from hooks.errors import SchemaError, SignatureError, WebhookError
from hooks.receipts import DeliveryLog, Receipt
from hooks.sign import verify

__all__ = [
    "DeliveryLog",
    "Receipt",
    "SchemaError",
    "SignatureError",
    "WebhookError",
    "accept",
    "verify",
]
