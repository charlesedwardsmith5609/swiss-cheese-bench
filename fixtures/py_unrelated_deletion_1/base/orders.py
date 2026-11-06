from datetime import datetime, timedelta

ORDERS: list[dict] = []


def list_orders(user_id):
    return [o for o in ORDERS if o["user"] == user_id]


def purge_expired(now=None):
    """Drop orders older than 30 days. Called nightly by the scheduler."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=30)
    ORDERS[:] = [o for o in ORDERS if o["created"] >= cutoff]
    return len(ORDERS)
