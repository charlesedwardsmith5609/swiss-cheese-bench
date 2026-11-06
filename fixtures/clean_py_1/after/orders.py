ORDERS: list[dict] = []


def list_orders(user_id, limit=50):
    return [o for o in ORDERS if o["user"] == user_id][:limit]
