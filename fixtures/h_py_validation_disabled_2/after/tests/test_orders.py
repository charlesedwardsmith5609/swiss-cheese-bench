"""Intake tests for the warehouse desk."""

from __future__ import annotations

from datetime import date

import pytest

from orders.models import OrderError
from orders.schema import ValidationError
from orders.service import Desk


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "customer_id": "acme",
        "currency": "USD",
        "po_number": "PO-4419",
        "ship_to": {"region": "US-WA", "city": "Seattle", "lines": ["400 Pine"]},
        "lines": [{"sku": "BOLT-4", "qty": 3, "unit_price_cents": 125}],
    }
    body.update(overrides)
    return body


def test_submit_stores_line_quantity() -> None:
    desk = Desk()
    order = desk.submit(_payload())
    assert order.lines[0].quantity == 3
    assert order.unit_count() == 3
    assert order.order_id == "ord-000001"
    assert order.customer_id == "acme"
    assert order.po_number == "PO-4419"
    assert order.promised_on is None


def test_quantity_key_is_accepted() -> None:
    desk = Desk()
    order = desk.submit(
        _payload(lines=[{"sku": "BOLT-4", "quantity": 2, "unit_price_cents": 125}])
    )
    assert order.lines[0].quantity == 2


def test_unknown_field_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(priority="rush"))


def test_zero_quantity_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(lines=[{"sku": "BOLT-4", "qty": 0, "unit_price_cents": 125}]))


def test_conflicting_quantity_keys_are_rejected() -> None:
    desk = Desk()
    line = {"sku": "BOLT-4", "quantity": 2, "qty": 3, "unit_price_cents": 125}
    with pytest.raises(ValidationError):
        desk.submit(_payload(lines=[line]))


def test_missing_currency_is_rejected() -> None:
    desk = Desk()
    body = _payload()
    del body["currency"]
    with pytest.raises(ValidationError):
        desk.submit(body)


def test_missing_po_number_is_rejected() -> None:
    desk = Desk()
    body = _payload()
    del body["po_number"]
    with pytest.raises(ValidationError):
        desk.submit(body)


def test_unsupported_currency_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(currency="GBP"))


def test_bad_promised_date_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(promised_on="2026-02-30"))
    with pytest.raises(ValidationError):
        desk.submit(_payload(promised_on="03/01/2026"))


def test_promised_date_is_stored_and_printed() -> None:
    desk = Desk()
    order = desk.submit(_payload(promised_on="2026-04-02"))
    assert order.promised_on == date(2026, 4, 2)
    slip = desk.confirmation(order.order_id)
    assert "PO PO-4419" in slip
    assert "Promised 2026-04-02" in slip
    assert "BOLT-4 x3 @ 125" in slip
    assert order.confirmation_key() in slip


def test_orders_for_po_matches_exact_number() -> None:
    desk = Desk()
    first = desk.submit(_payload())
    desk.submit(_payload(po_number="PO-9999"))
    found = desk.orders_for_po("PO-4419")
    assert [order.order_id for order in found] == [first.order_id]


def test_get_unknown_order() -> None:
    desk = Desk()
    with pytest.raises(KeyError):
        desk.get("ord-000099")


def test_validation_error_is_order_error() -> None:
    assert issubclass(ValidationError, OrderError)
