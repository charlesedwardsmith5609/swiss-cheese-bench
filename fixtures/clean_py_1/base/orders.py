ORDERS: list[dict] = []


def list_orders(user_id):
    return [o for o in ORDERS if o["user"] == user_id]
