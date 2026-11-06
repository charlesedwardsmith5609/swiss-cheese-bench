"""Drafts and the invoices posted from them.

Amounts are integer cents. tax_bps is a rate in basis points (10_000 is 100%).
The ledger owns each Invoice after issue returns; callers own the Draft.
account_id is the billing account key, and posted_by is the clerk.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineItem:
    """A group of units of one sku.

    unit_cents is the net price. tax_bps is the line tax rate in basis points.
    """

    sku: str
    description: str
    quantity: int
    unit_cents: int
    tax_bps: int = 0

    def net_cents(self) -> int:
        return self.quantity * self.unit_cents

    def tax_cents(self) -> int:
        return self.net_cents() * self.tax_bps // 10_000


@dataclass
class Draft:
    """An unposted invoice. account_id is the billing account key."""

    account_id: str
    currency: str
    lines: list[LineItem] = field(default_factory=list)
    memo: str = ""

    def subtotal_cents(self) -> int:
        return sum(line.net_cents() for line in self.lines)

    def tax_cents(self) -> int:
        return sum(line.tax_cents() for line in self.lines)


@dataclass(frozen=True)
class Invoice:
    """A posted invoice.

    number is unique and assigned by the ledger. posted_by is the clerk who
    issued it. total_cents is subtotal plus tax.
    """

    number: str
    account_id: str
    currency: str
    lines: tuple[LineItem, ...]
    memo: str
    subtotal_cents: int
    tax_cents: int
    issued_at: int
    posted_by: str

    def total_cents(self) -> int:
        return self.subtotal_cents + self.tax_cents
