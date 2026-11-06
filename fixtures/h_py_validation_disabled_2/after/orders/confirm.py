"""Desk confirmation text for a submitted order."""

from __future__ import annotations

from orders.models import Order


def render_confirmation(order: Order) -> str:
    """Plain-text slip the desk prints after intake.

    The purchase-order number and the promised date sit under the order id
    so the floor can match the buyer's paperwork.
    """
    rows = [
        f"{line.sku} x{line.quantity} @ {line.unit_price_cents}" for line in order.lines
    ]
    body = "\n".join(rows)
    if order.promised_on is None:
        promised = "unscheduled"
    else:
        promised = order.promised_on.isoformat()
    return (
        f"Order {order.confirmation_key()}\n"
        f"PO {order.po_number}\n"
        f"Customer {order.customer_id}\n"
        f"Currency {order.currency}\n"
        f"Promised {promised}\n"
        f"{body}\n"
        f"Units {order.unit_count()}\n"
    )
