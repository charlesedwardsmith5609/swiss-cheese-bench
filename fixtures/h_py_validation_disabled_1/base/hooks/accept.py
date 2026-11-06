"""Accept a verified webhook body and record a receipt.

The caller checks the signature before calling ``accept`` and owns the log.
This module does not keep process-wide state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hooks.receipts import Receipt, ReceiptLog
from hooks.schema import V1_SCHEMA


def accept(body: Mapping[str, Any], log: ReceiptLog) -> Receipt:
    """Validate ``body`` and store a receipt. A repeated id returns the first copy."""
    parsed = V1_SCHEMA.validate(body)
    receipt = Receipt(
        event_id=parsed["event_id"],
        event_type=parsed["event_type"],
        customer_id=parsed["customer_id"],
        amount_cents=parsed["amount_cents"],
        created=parsed["created"],
    )
    return log.put(receipt)
