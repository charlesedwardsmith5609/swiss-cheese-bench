"""Drafts and the invoices posted from them.

Amounts are integer cents. The ledger owns each Invoice after issue returns;
callers own the Draft they pass in.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineItem:
    """A group of units of one sku. unit_cents is the net price."""

    sku: str
    description: str
    quantity: int
    unit_cents: int

    def net_cents(self) -> int:
        return self.quantity * self.unit_cents


@dataclass
class Draft:
    """An unposted invoice. customer_id is the billing account key."""

    customer_id: str
    currency: str
    lines: list[LineItem] = field(default_factory=list)
    memo: str = ""

    def subtotal_cents(self) -> int:
        return sum(line.net_cents() for line in self.lines)


@dataclass(frozen=True)
class Invoice:
    """A posted invoice. number is unique and assigned by the ledger."""

    number: str
    customer_id: str
    currency: str
    lines: tuple[LineItem, ...]
    memo: str
    subtotal_cents: int
    issued_at: int

    def total_cents(self) -> int:
        return self.subtotal_cents
