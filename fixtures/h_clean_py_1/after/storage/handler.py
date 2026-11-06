"""HTTP-free upload handler.

One thread owns a handler and its store. ``handle`` is the only entry point.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from storage.metrics import Counter
from storage.policy import UploadPolicy, accept_type, permitted, validate_key, validate_policy
from storage.store import MemoryObjectStore

_SERVICE_TYPES = ("application/pdf", "image/png", "text/plain")


@dataclass(frozen=True)
class UploadRequest:
    """One upload submitted by a principal."""

    principal: str
    key: str
    body: bytes
    content_type: str = ""
    checksum: str = ""


@dataclass(frozen=True)
class UploadResult:
    """Result of a stored upload."""

    status: int
    key: str
    size: int
    content_type: str


class UploadRejected(Exception):
    """The upload was refused and nothing was written."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class UploadHandler:
    """Store an object after access, type, size, and checksum checks."""

    def __init__(
        self,
        store: MemoryObjectStore,
        policy: UploadPolicy | None = None,
    ) -> None:
        if policy is None:
            policy = UploadPolicy(allowed_types=_SERVICE_TYPES)
        self._policy = validate_policy(policy)
        self._store = store
        self.failures = Counter("upload.store_failure")

    def handle(self, request: UploadRequest) -> UploadResult:
        """Validate the request and write the body."""
        if not permitted(request.principal, "object:Put"):
            raise UploadRejected(403, "principal is not allowed to upload")
        key = _clean_key(request.key)
        body = request.body
        if not isinstance(body, (bytes, bytearray)):
            raise UploadRejected(400, "body must be bytes")
        media = _clean_type(self._policy, request.content_type)
        if len(body) > self._policy.max_bytes:
            raise UploadRejected(413, "object exceeds the size limit")
        _verify_checksum(body, request.checksum)
        payload = bytes(body)
        try:
            self._store.put(key, payload)
        except Exception:
            self.failures.increment()
            raise
        return UploadResult(
            status=201, key=key, size=len(payload), content_type=media
        )


def _clean_key(key: str) -> str:
    try:
        return validate_key(key)
    except ValueError as exc:
        raise UploadRejected(400, str(exc)) from exc


def _clean_type(policy: UploadPolicy, content_type: str) -> str:
    try:
        return accept_type(policy, content_type)
    except ValueError as exc:
        raise UploadRejected(415, str(exc)) from exc


def _verify_checksum(body: bytes, header: str) -> None:
    token = header.strip().lower()
    prefix = "sha256="
    if not token.startswith(prefix):
        raise UploadRejected(400, "checksum must be a sha-256 digest")
    digest = token[len(prefix) :]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise UploadRejected(400, "checksum must be a sha-256 digest")
    actual = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(actual, digest):
        raise UploadRejected(400, "checksum does not match the body")
