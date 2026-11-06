"""Resolve bearer tokens and operator rights for dispatcher requests."""

from __future__ import annotations

from notify.models import Principal, Role

TOKENS: dict[str, Principal] = {
    "token-acme-member": Principal("user-m", "acme", Role.MEMBER, "token-acme-member"),
    "token-acme-operator": Principal("user-o", "acme", Role.OPERATOR, "token-acme-operator"),
    "token-globex-member": Principal("user-g", "globex", Role.MEMBER, "token-globex-member"),
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


def require_operator(principal: Principal) -> None:
    """Allow the request only when the caller operates the tenant mailbox."""
    if principal.role != Role.OPERATOR:
        raise AuthError(403, "operator role required")
