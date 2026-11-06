"""Receiver tests for signed build notifications."""

from __future__ import annotations

import json
from typing import Any

import pytest

from webhooks import (
    MemoryLedger,
    Receipt,
    ReplayError,
    SignatureError,
    ValidationError,
    accept_delivery,
    sign_body,
)

_SECRET = b"test-secret"


def _body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _accept(payload: dict[str, Any], ledger: MemoryLedger | None = None) -> Receipt:
    raw = _body(payload)
    return accept_delivery(
        payload,
        body=raw,
        signature=sign_body(_SECRET, raw),
        secret=_SECRET,
        ledger=ledger if ledger is not None else MemoryLedger(),
    )


def _build(*, delivery_id: str = "del_build_1", **data: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "repository": "acme/billing",
        "status": "success",
        "revision": "a" * 40,
    }
    body.update(data)
    return {
        "id": delivery_id,
        "type": "build.finished",
        "created": 1_700_000_000,
        "data": body,
    }


def test_accepts_build_finished() -> None:
    receipt = _accept(_build())
    assert receipt.delivery_id == "del_build_1"
    assert receipt.event_type == "build.finished"
    assert receipt.created == 1_700_000_000
    assert receipt.repository == "acme/billing"
    assert receipt.status == "success"
    assert receipt.revision == "a" * 40


def test_rejects_unknown_data_field() -> None:
    payload = _build(delivery_id="del_unknown", logs_url="https://ci.example/logs/1")
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        _accept(_build(delivery_id="del_status", status="passed"))


def test_requires_repository() -> None:
    payload = _build(delivery_id="del_repo")
    del payload["data"]["repository"]
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_short_revision() -> None:
    with pytest.raises(ValidationError):
        _accept(_build(delivery_id="del_sha", revision="9f3c1a2b"))


def test_rejects_bool_timestamp() -> None:
    payload = _build(delivery_id="del_created")
    payload["created"] = True
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_bad_signature() -> None:
    payload = _build(delivery_id="del_sig")
    raw = _body(payload)
    signature = sign_body(_SECRET, raw)
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    with pytest.raises(SignatureError):
        accept_delivery(
            payload,
            body=raw,
            signature=flipped,
            secret=_SECRET,
            ledger=MemoryLedger(),
        )


def test_rejects_replay() -> None:
    ledger = MemoryLedger()
    payload = _build(delivery_id="del_replay")
    _accept(payload, ledger)
    with pytest.raises(ReplayError):
        _accept(payload, ledger)
