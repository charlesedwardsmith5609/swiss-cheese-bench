"""Acceptance tests for v1 flat bodies and v2 envelopes."""

from __future__ import annotations

import pytest

from hooks.accept import accept
from hooks.errors import SchemaError
from hooks.receipts import DeliveryLog


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
    receipt = accept(_body(), DeliveryLog())
    assert receipt.event_id == "evt_100"
    assert receipt.amount_cents == 2500
    assert receipt.duplicate is False


def test_replay_is_duplicate() -> None:
    log = DeliveryLog()
    first = accept(_body(), log)
    second = accept(_body(), log)
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.amount_cents == 2500


def test_rejects_unknown_field() -> None:
    with pytest.raises(SchemaError):
        accept(_body(livemode=True), DeliveryLog())


def test_rejects_missing_amount() -> None:
    body = _body()
    del body["amount_cents"]
    with pytest.raises(SchemaError):
        accept(body, DeliveryLog())


def test_rejects_negative_amount() -> None:
    with pytest.raises(SchemaError):
        accept(_body(amount_cents=-1), DeliveryLog())


def test_rejects_unknown_event_type() -> None:
    with pytest.raises(SchemaError):
        accept(_body(event_type="customer.deleted"), DeliveryLog())


@pytest.mark.parametrize("event_type", ["invoice.paid", "charge.refunded"])
def test_v1_accepts_added_event_types(event_type: str) -> None:
    receipt = accept(_body(event_type=event_type), DeliveryLog())
    assert receipt.event_type == event_type
    assert receipt.attempt == 1


def _v2(
    event_type: str,
    resource: dict[str, object],
    **extra: object,
) -> dict[str, object]:
    body: dict[str, object] = {
        "id": "evt_200",
        "type": event_type,
        "created": 1_700_000_100,
        "data": {"object": resource},
    }
    body.update(extra)
    return body


def test_v2_invoice_paid_records_attempt_and_version() -> None:
    resource = {
        "customer": "cus_9",
        "amount_cents": 2500,
        "currency": "usd",
        "hosted_invoice_url": "https://pay.example/invoices/evt_200",
        "lines": [{"id": "il_1", "amount": 2500}],
    }
    body = _v2(
        "invoice.paid",
        resource,
        api_version="2024-11-01",
        request={"id": "req_9", "attempt": 2},
    )
    receipt = accept(body, DeliveryLog())
    assert receipt.event_id == "evt_200"
    assert receipt.customer_id == "cus_9"
    assert receipt.amount_cents == 2500
    assert receipt.api_version == "2024-11-01"
    assert receipt.attempt == 2


def test_v2_charge_refunded_defaults_attempt_when_request_absent() -> None:
    resource = {
        "customer": "cus_3",
        "amount_cents": 500,
        "currency": "eur",
        "balance_transaction": "txn_44",
        "reason": "requested_by_customer",
    }
    receipt = accept(
        _v2("charge.refunded", resource, id="evt_201", created=1_700_000_200),
        DeliveryLog(),
    )
    assert receipt.event_type == "charge.refunded"
    assert receipt.amount_cents == 500
    assert receipt.customer_id == "cus_3"
    assert receipt.attempt == 1
    assert receipt.api_version == ""


def test_v2_rejects_unknown_data_member() -> None:
    body = {
        "id": "evt_204",
        "type": "invoice.paid",
        "created": 1_700_000_100,
        "data": {
            "object": {"customer": "cus_9", "amount_cents": 10, "currency": "usd"},
            "previous_attributes": {"amount_cents": 0},
        },
    }
    with pytest.raises(SchemaError):
        accept(body, DeliveryLog())
