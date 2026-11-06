"""Acceptance tests for flat webhook bodies."""

from __future__ import annotations

import pytest

from hooks.receipts import ReceiptLog
from hooks.errors import SchemaError
from hooks.accept import accept


def _body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_id": "evt_100",
        "event_type": "invoice.created",
        "customer_id": "cus_9",
        "amount_cents": 2500,
        "created": 1_700_000_000,
    }
    payload.update(overrides)
    return payload


def test_accepts_invoice_created() -> None:
    receipt = accept(_body(), ReceiptLog())
    assert receipt.event_id == "evt_100"
    assert receipt.amount_cents == 2500
    assert receipt.duplicate is False


def test_replay_is_duplicate() -> None:
    log = ReceiptLog()
    first = accept(_body(), log)
    second = accept(_body(), log)
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.amount_cents == 2500


def test_rejects_unknown_field() -> None:
    with pytest.raises(SchemaError):
        accept(_body(livemode=True), ReceiptLog())


def test_rejects_missing_amount() -> None:
    body = _body()
    del body["amount_cents"]
    with pytest.raises(SchemaError):
        accept(body, ReceiptLog())


def test_rejects_negative_amount() -> None:
    with pytest.raises(SchemaError):
        accept(_body(amount_cents=-1), ReceiptLog())


def test_rejects_unknown_event_type() -> None:
    with pytest.raises(SchemaError):
        accept(_body(event_type="customer.deleted"), ReceiptLog())
