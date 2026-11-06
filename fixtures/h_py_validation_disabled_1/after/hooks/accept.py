"""Accept a verified webhook body and record a receipt.

The caller checks the signature before calling ``accept`` and owns the log.
This module does not keep process-wide state. V1 bodies are flat; v2 bodies
carry the resource under ``data.object`` and may include a ``request``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hooks.receipts import DeliveryLog, Receipt
from hooks.schema import RESOURCE, V1_SCHEMA, V2_SCHEMA


def accept(body: Mapping[str, Any], log: DeliveryLog) -> Receipt:
    """Validate ``body`` and store a receipt. A repeated id returns the first copy."""
    if _is_v2(body):
        return _accept_v2(body, log)
    return _accept_v1(body, log)


def _is_v2(body: Mapping[str, Any]) -> bool:
    """V2 deliveries are the ones with an envelope id and a data object."""
    return isinstance(body, Mapping) and "id" in body and "data" in body


def _accept_v1(body: Mapping[str, Any], log: DeliveryLog) -> Receipt:
    parsed = V1_SCHEMA.validate(body)
    receipt = Receipt(
        event_id=parsed["event_id"],
        event_type=parsed["event_type"],
        customer_id=parsed["customer_id"],
        amount_cents=parsed["amount_cents"],
        created=parsed["created"],
    )
    return log.put(receipt)


def _accept_v2(body: Mapping[str, Any], log: DeliveryLog) -> Receipt:
    parsed = V2_SCHEMA.validate(body)
    resource = RESOURCE.validate(parsed["data"]["object"], reject_unknown=False)
    request = parsed["request"]
    attempt = 1 if request is None else request["attempt"]
    receipt = Receipt(
        event_id=parsed["id"],
        event_type=parsed["type"],
        customer_id=resource["customer"],
        amount_cents=resource["amount_cents"],
        created=parsed["created"],
        api_version=parsed["api_version"],
        attempt=attempt,
    )
    return log.put(receipt)
