import hmac

USERS = {"alice": "hunter2"}


def login(user, password):
    expected = USERS.get(user, "")
    return hmac.compare_digest(expected, password)
