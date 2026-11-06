"""Upload handler tests. Each case calls UploadHandler.handle."""

from __future__ import annotations

import hashlib

import pytest

from storage.handler import UploadHandler, UploadRejected, UploadRequest
from storage.policy import UploadPolicy
from storage.store import MemoryObjectStore


def _digest(body: bytes) -> str:
    return "sha256=" + hashlib.sha256(body).hexdigest()


def _request(
    body: bytes = b"hello",
    *,
    principal: str = "role:uploader",
    content_type: str = "text/plain",
    checksum: str | None = None,
    key: str = "docs/note.txt",
) -> UploadRequest:
    token = _digest(body) if checksum is None else checksum
    return UploadRequest(
        principal=principal,
        key=key,
        body=body,
        content_type=content_type,
        checksum=token,
    )


def test_uploader_stores_body() -> None:
    store = MemoryObjectStore()
    body = b"abc"
    result = UploadHandler(store).handle(
        _request(
            body,
            checksum="sha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )
    )
    assert result.status == 201
    assert result.key == "docs/note.txt"
    assert result.size == 3
    assert result.content_type == "text/plain"
    assert store.get("docs/note.txt") == body


def test_checksum_mismatch_writes_nothing() -> None:
    store = MemoryObjectStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(_request(checksum="sha256=" + ("ab" * 32)))
    assert caught.value.status == 400
    assert "docs/note.txt" not in store


def test_disallowed_type_writes_nothing() -> None:
    store = MemoryObjectStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(_request(content_type="image/gif"))
    assert caught.value.status == 415
    assert "docs/note.txt" not in store


def test_other_principal_is_rejected() -> None:
    store = MemoryObjectStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(
            UploadRequest(principal="role:reader", key="docs/note.txt", body=b"hello")
        )
    assert caught.value.status == 403
    assert "docs/note.txt" not in store


def test_parent_segment_is_rejected() -> None:
    store = MemoryObjectStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(
            UploadRequest(principal="role:uploader", key="../note.txt", body=b"hello")
        )
    assert caught.value.status == 400
    assert "note.txt" not in store


def test_handler_rejects_empty_allow_list() -> None:
    with pytest.raises(ValueError, match="allowed_types"):
        UploadHandler(MemoryObjectStore(), UploadPolicy())


class _FailingStore(MemoryObjectStore):
    """Test double that fails every write."""

    def put(self, key: str, body: bytes) -> None:
        raise OSError("disk full")


def test_store_failure_is_counted_and_propagated() -> None:
    handler = UploadHandler(_FailingStore())
    with pytest.raises(OSError, match="disk full"):
        handler.handle(_request())
    assert handler.failures.name == "upload.store_failure"
    assert handler.failures.value == 1
