"""Declarative checks for partner webhook bodies.

Schemas are immutable and shared across calls. Validation copies fields into
a new dict and does not mutate the payload it was given.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hooks.errors import SchemaError


@dataclass(frozen=True)
class Field:
    """One JSON member.

    ``choices`` constrains strings. ``minimum`` constrains integers. A missing
    key fails when ``required`` is set; otherwise ``default`` is returned.
    """

    name: str
    kind: Any
    required: bool = True
    default: Any = None
    choices: tuple[str, ...] = ()
    minimum: int | None = None


@dataclass(frozen=True)
class ObjectSchema:
    """A JSON object. Unknown keys fail closed when ``reject_unknown`` is set."""

    fields: tuple[Field, ...]
    reject_unknown: bool = True

    def validate(
        self,
        payload: Mapping[str, Any],
        *,
        reject_unknown: bool | None = None,
    ) -> dict[str, Any]:
        """Return the schema fields read from ``payload``."""
        if not isinstance(payload, Mapping):
            raise SchemaError("body must be an object")
        known = {field.name: field for field in self.fields}
        reject = self.reject_unknown if reject_unknown is None else reject_unknown
        if reject:
            extra = [key for key in payload if key not in known]
            if extra:
                raise SchemaError(f"unknown field {sorted(extra)[0]}")
        parsed: dict[str, Any] = {}
        for field in self.fields:
            parsed[field.name] = _read(field, payload)
        return parsed


def _read(field: Field, payload: Mapping[str, Any]) -> Any:
    if field.name not in payload:
        if field.required:
            raise SchemaError(f"missing {field.name}")
        return field.default
    value = payload[field.name]
    if isinstance(field.kind, ObjectSchema):
        if not isinstance(value, Mapping):
            raise SchemaError(f"{field.name} must be an object")
        return field.kind.validate(value)
    if field.kind is int and isinstance(value, bool):
        raise SchemaError(f"{field.name} must be an integer")
    if not isinstance(value, field.kind):
        raise SchemaError(f"{field.name} has the wrong type")
    if field.choices and value not in field.choices:
        raise SchemaError(f"{field.name} is not an allowed value")
    if field.minimum is not None and isinstance(value, int) and value < field.minimum:
        raise SchemaError(f"{field.name} is below the minimum")
    return value


EVENT_TYPES = ("invoice.created", "invoice.voided", "invoice.paid", "charge.refunded")

V1_SCHEMA = ObjectSchema(
    fields=(
        Field("event_id", str),
        Field("event_type", str, choices=EVENT_TYPES),
        Field("customer_id", str),
        Field("amount_cents", int, minimum=0),
        Field("created", int, minimum=0),
    ),
)

CURRENCIES = ("usd", "eur")


RESOURCE = ObjectSchema(
    fields=(
        Field("customer", str),
        Field("amount_cents", int, minimum=0),
        Field("currency", str, choices=CURRENCIES),
    ),
)

REQUEST = ObjectSchema(
    fields=(
        Field("id", str, required=False, default=""),
        Field("attempt", int, minimum=1),
    ),
)

DATA = ObjectSchema(
    fields=(Field("object", dict),),
)

V2_SCHEMA = ObjectSchema(
    fields=(
        Field("id", str),
        Field("type", str, choices=EVENT_TYPES),
        Field("created", int, minimum=0),
        Field("api_version", str, required=False, default=""),
        Field("data", DATA),
        Field("request", REQUEST, required=False, default=None),
    ),
)
