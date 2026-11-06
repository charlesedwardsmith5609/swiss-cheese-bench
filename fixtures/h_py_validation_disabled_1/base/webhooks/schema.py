"""Schema for inbound build webhooks.

Unknown keys are rejected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from webhooks.errors import ValidationError


@dataclass(frozen=True)
class Field:
    """One accepted key on an object."""

    name: str
    kind: str
    required: bool = True
    choices: frozenset[str] | None = None


_ENVELOPE: tuple[Field, ...] = (
    Field("id", "token"),
    Field("type", "token"),
    Field("created", "int"),
    Field("data", "object"),
)

_BUILD_FIELDS: tuple[Field, ...] = (
    Field("repository", "token"),
    Field(
        "status",
        "choice",
        choices=frozenset({"cancelled", "failure", "success"}),
    ),
    Field("revision", "sha"),
)

_EVENTS: dict[str, tuple[Field, ...]] = {
    "build.finished": _BUILD_FIELDS,
}


def parse_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a webhook body and return the receipt fields."""
    outer = _bind(payload, _ENVELOPE)
    kind = outer["type"]
    fields = _EVENTS.get(kind)
    if fields is None:
        raise ValidationError(f"unsupported event: {kind}")
    data = _bind(outer["data"], fields)
    return {
        "delivery_id": outer["id"],
        "event_type": kind,
        "created": outer["created"],
        "repository": data["repository"],
        "status": data["status"],
        "revision": data["revision"],
    }


def _bind(payload: Mapping[str, Any], fields: Sequence[Field]) -> dict[str, Any]:
    """Copy declared fields and reject anything else."""
    if not isinstance(payload, Mapping):
        raise ValidationError("expected an object")
    known = {field.name for field in fields}
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValidationError("unknown fields: " + ", ".join(unknown))
    bound: dict[str, Any] = {}
    for field in fields:
        if field.name not in payload:
            if field.required:
                raise ValidationError(f"{field.name} is required")
            continue
        bound[field.name] = _coerce(field, payload[field.name])
    return bound


def _coerce(field: Field, value: Any) -> Any:
    """Apply a field kind."""
    if field.kind == "token":
        return _coerce_token(field, value)
    if field.kind == "choice":
        return _coerce_choice(field, value)
    if field.kind == "int":
        return _coerce_int(field, value)
    if field.kind == "sha":
        return _coerce_sha(field, value)
    if field.kind == "object":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field.name} must be an object")
        return value
    raise ValidationError(f"unsupported kind for {field.name}")


def _coerce_token(field: Field, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field.name} must be a non-empty string")
    return value.strip()


def _coerce_choice(field: Field, value: Any) -> str:
    """Normalize a choice field to its canonical value."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field.name} must be a non-empty string")
    token = value.strip().lower()
    allowed = field.choices or frozenset()
    if token not in allowed:
        listed = ", ".join(sorted(allowed))
        raise ValidationError(f"{field.name} must be one of {listed}")
    return token


def _coerce_int(field: Field, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field.name} must be an integer")
    return value


def _coerce_sha(field: Field, value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field.name} must be a hex sha")
    token = value.strip().lower()
    if len(token) != 40 or any(char not in "0123456789abcdef" for char in token):
        raise ValidationError(f"{field.name} must be a 40-character hex sha")
    return token
