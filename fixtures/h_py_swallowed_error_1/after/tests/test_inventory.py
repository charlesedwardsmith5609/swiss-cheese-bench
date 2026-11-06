from decimal import Decimal

import pytest

from inventory.models import InventoryItem
from inventory.pricing import PriceBook, UnknownSku
from inventory.service import InsufficientStock, InventoryService


def item(
    sku: str = "CHAIR-1",
    *,
    category: str = "furniture",
    price: str = "20.00",
    available: int = 12,
) -> InventoryItem:
    return InventoryItem(
        sku=sku,
        category=category,
        unit_price=Decimal(price),
        available=available,
    )


def test_price_book_applies_volume_discount() -> None:
    book = PriceBook({"CHAIR-1": item()})

    line = book.quote_line("CHAIR-1", 10)

    assert line.unit_price == Decimal("19.00")
    assert line.subtotal == Decimal("190.00")
    assert line.net == Decimal("190.00")


def test_price_book_applies_category_adjustment() -> None:
    book = PriceBook(
        {"CHAIR-1": item()},
        adjustment_source=lambda: {"furniture": Decimal("0.10")},
    )

    line = book.quote_line("CHAIR-1", 2)

    assert line.adjustment_rate == Decimal("0.10")
    assert line.subtotal == Decimal("40.00")
    assert line.net == Decimal("44.00")


def test_quote_loads_adjustments_once_for_all_lines() -> None:
    calls = 0

    def adjustments() -> dict[str, Decimal]:
        nonlocal calls
        calls += 1
        return {
            "furniture": Decimal("0.10"),
            "lighting": Decimal("-0.05"),
        }

    book = PriceBook(
        {
            "CHAIR-1": item(),
            "LAMP-1": item(
                "LAMP-1",
                category="lighting",
                price="10.00",
            ),
        },
        adjustment_source=adjustments,
    )

    quote = book.quote({"CHAIR-1": 1, "LAMP-1": 2})

    assert calls == 1
    assert quote.subtotal == Decimal("40.00")
    assert quote.total == Decimal("41.00")


def test_quote_applies_country_tax_after_adjustments() -> None:
    book = PriceBook(
        {"CHAIR-1": item()},
        adjustment_source=lambda: {"furniture": Decimal("0.10")},
    )

    quote = book.quote({"CHAIR-1": 2}, country="CA")

    assert quote.subtotal == Decimal("40.00")
    assert quote.tax == Decimal("5.72")
    assert quote.total == Decimal("49.72")


def test_price_book_rejects_unknown_sku() -> None:
    book = PriceBook({})

    with pytest.raises(UnknownSku):
        book.quote_line("MISSING", 1)


def test_price_book_rejects_unsupported_country() -> None:
    book = PriceBook({"CHAIR-1": item()})

    with pytest.raises(ValueError, match="unsupported country"):
        book.quote({"CHAIR-1": 1}, country="FR")


def test_reserve_reduces_available_inventory() -> None:
    service = InventoryService(
        {"CHAIR-1": item()},
        adjustment_source=lambda: {"furniture": Decimal("0.10")},
    )

    quote = service.reserve({"CHAIR-1": 2}, country="GB")

    assert quote.total == Decimal("52.80")
    assert service.available("CHAIR-1") == 10


def test_failed_reservation_does_not_change_inventory() -> None:
    service = InventoryService({"CHAIR-1": item(available=1)})

    with pytest.raises(InsufficientStock):
        service.reserve({"CHAIR-1": 2})

    assert service.available("CHAIR-1") == 1
