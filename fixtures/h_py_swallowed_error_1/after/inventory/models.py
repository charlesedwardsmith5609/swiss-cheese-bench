from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class InventoryItem:
    """An item currently offered by the inventory service."""

    sku: str
    category: str
    unit_price: Decimal
    available: int


@dataclass(frozen=True)
class QuoteLine:
    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    adjustment_rate: Decimal
    net: Decimal


@dataclass(frozen=True)
class Quote:
    lines: tuple[QuoteLine, ...]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
