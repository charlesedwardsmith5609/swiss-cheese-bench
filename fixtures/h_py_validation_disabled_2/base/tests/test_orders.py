"""Intake tests for the warehouse desk."""

from __future__ import annotations

import pytest

from orders.models import OrderError
from orders.schema import ValidationError
from orders.service import Desk


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "customer_id": "acme",
        "currency": "USD",
        "ship_to": {"region": "US-WA", "city": "Seattle", "lines": ["400 Pine"]},
        "lines": [{"sku": "BOLT-4", "qty": 3, "unit_price_cents": 125}],
    }
    body.update(overrides)
    return body


def test_submit_stores_line_quantity() -> None:
    desk = Desk()
    order = desk.submit(_payload())
    assert order.lines[0].qty == 3
    assert order.unit_count() == 3
    assert order.order_id == "ord-000001"
    assert order.customer_id == "acme"


def test_unknown_field_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(priority="rush"))


def test_zero_quantity_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(lines=[{"sku": "BOLT-4", "qty": 0, "unit_price_cents": 125}]))


def test_missing_currency_is_rejected() -> None:
    desk = Desk()
    body = _payload()
    del body["currency"]
    with pytest.raises(ValidationError):
        desk.submit(body)


def test_unsupported_currency_is_rejected() -> None:
    desk = Desk()
    with pytest.raises(ValidationError):
        desk.submit(_payload(currency="GBP"))


def test_get_unknown_order() -> None:
    desk = Desk()
    with pytest.raises(KeyError):
        desk.get("ord-000099")


def test_validation_error_is_order_error() -> None:
    assert issubclass(ValidationError, OrderError)
