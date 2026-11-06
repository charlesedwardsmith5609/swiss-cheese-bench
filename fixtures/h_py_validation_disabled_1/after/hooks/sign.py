"""HMAC signatures over the raw webhook body.

``verify`` is pure. The caller owns the secret and the raw bytes; nothing
here is cached or shared.
"""

from __future__ import annotations

import hashlib
import hmac


def verify(secret: bytes, body: bytes, header: str) -> bool:
    """Return True when ``header`` is the hex digest of ``body`` under ``secret``."""
    if not secret or not header:
        return False
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, header.strip().lower())
