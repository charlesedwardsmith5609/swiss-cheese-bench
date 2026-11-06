"""Plain-text invoice statements.

The ledger owns a StatementWriter and calls render after an invoice is built.
Rendering does not touch the spool.
"""

from __future__ import annotations

from billing.models import Invoice


class StatementWriter:
    """Renders one posted invoice as text. Amounts stay in cents."""

    def render(self, invoice: Invoice) -> str:
        rows = [
            f"INVOICE {invoice.number}",
            f"customer {invoice.customer_id}",
            f"currency {invoice.currency}",
        ]
        if invoice.memo:
            rows.append(f"memo {invoice.memo}")
        for line in invoice.lines:
            rows.append(
                f"{line.sku} {line.description} "
                f"x{line.quantity} {line.net_cents()}"
            )
        rows.append(f"subtotal {invoice.subtotal_cents}")
        rows.append(f"total {invoice.total_cents()}")
        return "\n".join(rows) + "\n"
