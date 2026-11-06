"""Upload handler tests. Each case calls UploadHandler.handle."""

from __future__ import annotations

import pytest

from storage.handler import UploadHandler, UploadRejected, UploadRequest
from storage.store import MemoryBlobStore


def test_uploader_stores_body() -> None:
    store = MemoryBlobStore()
    result = UploadHandler(store).handle(
        UploadRequest(principal="role:uploader", key="docs/note.txt", body=b"hello")
    )
    assert result.status == 201
    assert result.key == "docs/note.txt"
    assert result.size == 5
    assert store.read("docs/note.txt") == b"hello"


def test_other_principal_is_rejected() -> None:
    store = MemoryBlobStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(
            UploadRequest(principal="role:reader", key="docs/note.txt", body=b"hello")
        )
    assert caught.value.status == 403
    assert "docs/note.txt" not in store


def test_parent_segment_is_rejected() -> None:
    store = MemoryBlobStore()
    with pytest.raises(UploadRejected) as caught:
        UploadHandler(store).handle(
            UploadRequest(principal="role:uploader", key="../note.txt", body=b"hello")
        )
    assert caught.value.status == 400
    assert "note.txt" not in store
