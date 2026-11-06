import secrets
import time

USERS: dict[str, str] = {}
TOKENS: dict[str, tuple[str, float]] = {}
EXPIRY_SECONDS = 15 * 60


def issue_token(email, now=None):
    token = secrets.token_urlsafe(32)
    TOKENS[token] = (email, (now or time.time()) + EXPIRY_SECONDS)
    return token


def redeem_token(token, new_password, now=None):
    entry = TOKENS.get(token)
    if entry is None:
        raise KeyError("unknown token")
    email, expires = entry
    if (now or time.time()) > expires:
        raise ValueError("token expired")
    USERS[email] = new_password
