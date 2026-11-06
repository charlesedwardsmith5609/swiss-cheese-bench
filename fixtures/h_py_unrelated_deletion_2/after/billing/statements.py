"""Plain-text invoice statements.

The ledger owns a StatementWriter and calls render after an invoice is built.
Each line shows its net and tax amounts in cents. A totals block lists
subtotal, tax, and total. Rendering does not touch the spool.
"""

from __future__ import annotations

from billing.models import Invoice, LineItem


class StatementWriter:
    """Renders one posted invoice as text. Amounts stay in cents."""

    def render(self, invoice: Invoice) -> str:
        parts: list[str] = [
            f"INVOICE {invoice.number}",
            f"account {invoice.account_id}",
            f"posted_by {invoice.posted_by}",
            f"currency {invoice.currency}",
        ]
        if invoice.memo:
            parts.append(f"memo {invoice.memo}")
        parts.append("lines")
        for line in invoice.lines:
            parts.append(self._line(line))
        parts.append("totals")
        parts.append(f"subtotal {invoice.subtotal_cents}")
        parts.append(f"tax {invoice.tax_cents}")
        parts.append(f"total {invoice.total_cents()}")
        return "\n".join(parts) + "\n"

    def _line(self, line: LineItem) -> str:
        return (
            f"{line.sku} {line.description} x{line.quantity} "
            f"net {line.net_cents()} tax {line.tax_cents()}"
        )
