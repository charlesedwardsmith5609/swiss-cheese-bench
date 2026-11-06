from decimal import Decimal

import pytest

from inventory.models import InventoryItem
from inventory.pricing import PriceBook, UnknownSku
from inventory.service import InsufficientStock, InventoryService


def item(
    sku: str = "CHAIR-1",
    *,
    price: str = "20.00",
    available: int = 12,
) -> InventoryItem:
    return InventoryItem(
        sku=sku,
        category="furniture",
        unit_price=Decimal(price),
        available=available,
    )


def test_price_book_applies_volume_discount() -> None:
    book = PriceBook({"CHAIR-1": item()})

    line = book.quote_line("CHAIR-1", 10)

    assert line.unit_price == Decimal("19.00")
    assert line.subtotal == Decimal("190.00")


def test_price_book_rejects_unknown_sku() -> None:
    book = PriceBook({})

    with pytest.raises(UnknownSku):
        book.quote_line("MISSING", 1)


def test_reserve_reduces_available_inventory() -> None:
    service = InventoryService({"CHAIR-1": item()})

    quote = service.reserve({"CHAIR-1": 2})

    assert quote.total == Decimal("40.00")
    assert service.available("CHAIR-1") == 10


def test_failed_reservation_does_not_change_inventory() -> None:
    service = InventoryService({"CHAIR-1": item(available=1)})

    with pytest.raises(InsufficientStock):
        service.reserve({"CHAIR-1": 2})

    assert service.available("CHAIR-1") == 1
