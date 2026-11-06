from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    sku: str
    unit_price: Decimal
    currency: str = "USD"


@dataclass(frozen=True)
class QuoteLineRequest:
    sku: str
    quantity: int

    def validate(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku is required")
        if self.quantity < 1:
            raise ValueError("quantity must be positive")


@dataclass(frozen=True)
class QuoteRequest:
    lines: tuple[QuoteLineRequest, ...] = ()
    currency: str = "USD"
    warehouse: str = ""

    def validate(self) -> None:
        if not self.lines:
            raise ValueError("at least one quote line is required")
        if not self.currency.strip():
            raise ValueError("currency is required")
        for line in self.lines:
            line.validate()

    def normalized_warehouse(self) -> str:
        return self.warehouse.strip() or "primary"


@dataclass(frozen=True)
class QuoteLine:
    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
