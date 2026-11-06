"""Object keys, content types, and action rules.

Key checks reject empty segments, parent traversal, and absolute paths.
The allow list stays empty until validate_policy has accepted it.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_BYTES = 5_242_880
MAX_KEY_LENGTH = 256


@dataclass(frozen=True)
class UploadPolicy:
    """Empty allow list is rejected by validate_policy."""

    allowed_types: tuple[str, ...] = ()
    max_bytes: int = MAX_BYTES


@dataclass(frozen=True)
class AccessRule:
    """One explicit allow or deny. Action patterns may end in ``*``."""

    effect: str
    actions: tuple[str, ...]
    principals: tuple[str, ...]


# Every principal is denied delete. The uploader role may put and get.
RULES: tuple[AccessRule, ...] = (
    AccessRule("Deny", ("object:Delete*",), ("*",)),
    AccessRule("Allow", ("object:Put", "object:Get"), ("role:uploader",)),
)


def validate_policy(policy: UploadPolicy) -> UploadPolicy:
    """Reject an empty allow list and normalise type tokens."""
    if not policy.allowed_types:
        raise ValueError("allowed_types must list at least one content type")
    if policy.max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    seen: list[str] = []
    for raw in policy.allowed_types:
        token = raw.strip().lower()
        if not token or "/" not in token or " " in token or token.startswith("/"):
            raise ValueError("content types must be type/subtype")
        if token not in seen:
            seen.append(token)
    return UploadPolicy(allowed_types=tuple(seen), max_bytes=policy.max_bytes)


def accept_type(policy: UploadPolicy, content_type: str) -> str:
    """Return the media type when it is listed."""
    if not isinstance(content_type, str):
        raise ValueError("content type must be a string")
    media = content_type.split(";", 1)[0].strip().lower()
    if not media:
        raise ValueError("content type is required")
    if media not in policy.allowed_types:
        raise ValueError("content type is not allowed")
    return media


def _covers(pattern: str, value: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith("*") and pattern[:-1]:
        return value.startswith(pattern[:-1])
    return pattern == value


def permitted(principal: str, action: str) -> bool:
    """True when an Allow matches and no Deny matches."""
    allowed = False
    for rule in RULES:
        principals = any(_covers(item, principal) for item in rule.principals)
        actions = any(_covers(item, action) for item in rule.actions)
        if not principals or not actions:
            continue
        if rule.effect == "Deny":
            return False
        if rule.effect == "Allow":
            allowed = True
    return allowed


def validate_key(key: str) -> str:
    """Return a cleaned object key or raise ValueError."""
    if not isinstance(key, str):
        raise ValueError("object key must be a string")
    cleaned = key.strip()
    if not cleaned or len(cleaned) > MAX_KEY_LENGTH:
        raise ValueError("object key is invalid")
    if cleaned.startswith("/") or "\\" in cleaned:
        raise ValueError("object key is invalid")
    parts = cleaned.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("object key is invalid")
    return cleaned
