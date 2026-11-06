import re

PHONE_RE = re.compile(r"^\+\d{10,14}$")


def validate_user(data):
    if not data.get("name"):
        raise ValueError("name required")
    if not PHONE_RE.match(data.get("phone", "")):
        raise ValueError("invalid phone")
    return data
