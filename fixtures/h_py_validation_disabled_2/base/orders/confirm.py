"""Desk confirmation text for a submitted order."""

from __future__ import annotations

from orders.models import Order


def render_confirmation(order: Order) -> str:
    """Plain-text slip the desk prints after intake."""
    rows = [f"{line.sku} x{line.qty} @ {line.unit_price_cents}" for line in order.lines]
    body = "\n".join(rows)
    return (
        f"Order {order.order_id}\n"
        f"Customer {order.customer_id}\n"
        f"Currency {order.currency}\n"
        f"{body}\n"
        f"Units {order.unit_count()}\n"
    )
