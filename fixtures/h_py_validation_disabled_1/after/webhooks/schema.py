"""Schema for inbound build and deployment webhooks.

Unknown keys are rejected. Deployment callbacks accept `target` as `environment`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from webhooks.errors import ValidationError

_UNSET = object()


@dataclass(frozen=True)
class Field:
    """One accepted key on an object."""

    name: str
    kind: str
    required: bool = True
    choices: frozenset[str] | None = None
    aliases: tuple[str, ...] = ()
    synonyms: tuple[tuple[str, str], ...] = ()
    default: Any = _UNSET
    minimum: int | None = None
    maximum: int | None = None


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

_DEPLOY_FIELDS: tuple[Field, ...] = (
    Field("environment", "token", aliases=("target",)),
    Field("service", "token"),
    Field(
        "state",
        "choice",
        choices=frozenset({"failure", "success"}),
        synonyms=(("error", "failure"), ("failed", "failure")),
        default="success",
    ),
    Field("revision", "sha", minimum=7, maximum=40),
    Field("attempt", "int", required=False, default=1, minimum=1),
)

_EVENTS: dict[str, tuple[Field, ...]] = {
    "build.finished": _BUILD_FIELDS,
    "deployment.finished": _DEPLOY_FIELDS,
}


def parse_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a webhook body and return the receipt fields."""
    outer = _bind(payload, _ENVELOPE)
    kind = outer["type"]
    fields = _EVENTS.get(kind)
    if fields is None:
        raise ValidationError(f"unsupported event: {kind}")
    data = _bind(outer["data"], fields)
    if kind == "build.finished":
        return {
            "delivery_id": outer["id"],
            "event_type": kind,
            "created": outer["created"],
            "repository": data["repository"],
            "status": data["status"],
            "revision": data["revision"],
        }
    return {
        "delivery_id": outer["id"],
        "event_type": kind,
        "created": outer["created"],
        "status": data["state"],
        "revision": data["revision"],
        "environment": data["environment"],
        "service": data["service"],
        "attempt": data["attempt"],
    }


def _bind(payload: Mapping[str, Any], fields: Sequence[Field]) -> dict[str, Any]:
    """Copy declared fields and reject anything else."""
    if not isinstance(payload, Mapping):
        raise ValidationError("expected an object")
    known = _known_keys(fields)
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValidationError("unknown fields: " + ", ".join(unknown))
    bound: dict[str, Any] = {}
    for field in fields:
        raw = _lookup(payload, field)
        if raw is _UNSET:
            if field.required:
                raise ValidationError(f"{field.name} is required")
            if field.default is _UNSET:
                continue
            raw = field.default
        bound[field.name] = _coerce(field, raw)
    return bound


def _known_keys(fields: Sequence[Field]) -> set[str]:
    """Names that may appear on the object, including legacy aliases."""
    known = {field.name for field in fields}
    for field in fields:
        known.update(field.aliases)
    return known


def _lookup(payload: Mapping[str, Any], field: Field) -> Any:
    """Resolve a field from its canonical name or a legacy alias."""
    found: list[Any] = []
    if field.name in payload:
        found.append(payload[field.name])
    for alias in field.aliases:
        if alias in payload:
            found.append(payload[alias])
    if not found:
        return _UNSET
    if any(item != found[0] for item in found[1:]):
        raise ValidationError(f"{field.name} conflicts with an alias")
    return found[0]


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
    if token in allowed:
        return token
    translated = dict(field.synonyms).get(token)
    if translated is not None:
        if translated not in allowed:
            raise ValidationError(f"{field.name} synonym is not allowed")
        return translated
    if field.default is not _UNSET:
        return str(field.default)
    listed = ", ".join(sorted(allowed))
    raise ValidationError(f"{field.name} must be one of {listed}")


def _coerce_int(field: Field, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field.name} must be an integer")
    if field.minimum is not None and value < field.minimum:
        raise ValidationError(f"{field.name} must be >= {field.minimum}")
    if field.maximum is not None and value > field.maximum:
        raise ValidationError(f"{field.name} must be <= {field.maximum}")
    return value


def _coerce_sha(field: Field, value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field.name} must be a hex sha")
    token = value.strip().lower()
    low = 40 if field.minimum is None else field.minimum
    high = 40 if field.maximum is None else field.maximum
    bad_width = len(token) < low or len(token) > high
    bad_digit = any(char not in "0123456789abcdef" for char in token)
    if bad_width or bad_digit:
        if low == 40 and high == 40:
            raise ValidationError(f"{field.name} must be a 40-character hex sha")
        raise ValidationError(
            f"{field.name} must be a hex sha of {low} to {high} characters"
        )
    return token
