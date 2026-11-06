"""Accept signed webhook deliveries once."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from webhooks.errors import ReplayError, SignatureError
from webhooks.schema import parse_event


@dataclass(frozen=True)
class Receipt:
    """A delivery that passed signature, schema, and replay checks."""

    delivery_id: str
    event_type: str
    created: int
    repository: str
    status: str
    revision: str


class MemoryLedger:
    """Set of delivery ids accepted so far.

    The caller owns the ledger and must not share it across threads.
    """

    def __init__(self) -> None:
        self._ids: set[str] = set()

    def remember(self, delivery_id: str) -> None:
        """Reject a repeated delivery id, otherwise record it."""
        if delivery_id in self._ids:
            raise ReplayError(f"replayed delivery: {delivery_id}")
        self._ids.add(delivery_id)

    def __contains__(self, delivery_id: object) -> bool:
        return delivery_id in self._ids


def sign_body(secret: bytes, body: bytes) -> str:
    """Return the sha256= signature header for a raw body."""
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def verify_signature(secret: bytes, body: bytes, header: str) -> None:
    """Raise SignatureError when the header does not match the body."""
    expected = sign_body(secret, body)
    if not hmac.compare_digest(expected, header):
        raise SignatureError("signature mismatch")


def accept_delivery(
    payload: Mapping[str, Any],
    *,
    body: bytes,
    signature: str,
    secret: bytes,
    ledger: MemoryLedger,
) -> Receipt:
    """Verify the raw body, validate the decoded payload, and record the delivery.

    ``body`` is the exact byte string covered by ``signature``. ``payload`` is
    that JSON value already decoded by the caller.
    """
    verify_signature(secret, body, signature)
    parsed = parse_event(payload)
    ledger.remember(parsed["delivery_id"])
    return Receipt(
        delivery_id=parsed["delivery_id"],
        event_type=parsed["event_type"],
        created=parsed["created"],
        repository=parsed["repository"],
        status=parsed["status"],
        revision=parsed["revision"],
    )
