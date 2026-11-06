"""HTTP-free upload handler.

One thread owns a handler and its store. ``handle`` is the only entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

from storage.policy import MAX_BYTES, validate_key
from storage.store import MemoryBlobStore


@dataclass(frozen=True)
class UploadRequest:
    """One upload submitted by a principal."""

    principal: str
    key: str
    body: bytes
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class UploadResult:
    """Result of a stored upload."""

    status: int
    key: str
    size: int


class UploadRejected(Exception):
    """The upload was refused and nothing was written."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class UploadHandler:
    """Store an object for the uploader role after key and size checks."""

    def __init__(self, store: MemoryBlobStore) -> None:
        self._store = store

    def handle(self, request: UploadRequest) -> UploadResult:
        """Validate the request and write the body."""
        if request.principal != "role:uploader":
            raise UploadRejected(403, "principal is not allowed to upload")
        key = _clean_key(request.key)
        body = request.body
        if not isinstance(body, (bytes, bytearray)):
            raise UploadRejected(400, "body must be bytes")
        if len(body) > MAX_BYTES:
            raise UploadRejected(413, "object exceeds the size limit")
        self._store.write(key, bytes(body))
        return UploadResult(status=201, key=key, size=len(body))


def _clean_key(key: str) -> str:
    try:
        return validate_key(key)
    except ValueError as exc:
        raise UploadRejected(400, str(exc)) from exc
