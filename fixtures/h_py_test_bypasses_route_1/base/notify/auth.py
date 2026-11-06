"""Resolve bearer tokens to a tenant-scoped principal."""

from __future__ import annotations

from notify.models import Principal

TOKENS: dict[str, Principal] = {
    "token-acme-member": Principal("user-m", "acme", "token-acme-member"),
    "token-acme-operator": Principal("user-o", "acme", "token-acme-operator"),
    "token-globex-member": Principal("user-g", "globex", "token-globex-member"),
}


class AuthError(Exception):
    """Authentication failed before a handler ran."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def resolve(authorization: str | None) -> Principal:
    """Return the principal for a raw Authorization header value."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    principal = TOKENS.get(token)
    if principal is None:
        raise AuthError(401, "unknown token")
    return principal
