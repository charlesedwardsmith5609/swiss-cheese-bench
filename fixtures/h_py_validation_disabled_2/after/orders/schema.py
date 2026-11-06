"""Intake schema for desk orders.

Unknown keys are rejected. A legacy line key is accepted as an alias of the
warehouse quantity for this release. Promised dates are calendar days.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from orders.models import LineItem, OrderError, ShipTo


class ValidationError(OrderError):
    """The payload does not match the intake schema."""


_MISSING = object()


@dataclass(frozen=True)
class Field:
    """One accepted key on a payload object."""

    name: str
    kind: str
    required: bool = True
    minimum: int | None = None
    aliases: tuple[str, ...] = ()


ORDER_FIELDS: tuple[Field, ...] = (
    Field("customer_id", "str"),
    Field("currency", "str"),
    Field("po_number", "str"),
    Field("promised_on", "date", required=False),
    Field("ship_to", "object"),
    Field("lines", "list"),
)

LINE_FIELDS: tuple[Field, ...] = (
    Field("sku", "str"),
    Field("quantity", "int", minimum=1, aliases=("qty",)),
    Field("unit_price_cents", "int", minimum=0),
)

SHIP_FIELDS: tuple[Field, ...] = (
    Field("region", "str"),
    Field("city", "str"),
    Field("lines", "str_list", required=False),
)

_CURRENCIES = frozenset({"USD", "CAD", "EUR"})
_DATE_FORMAT = "%Y-%m-%d"


def parse_order(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an intake document and return normalized pieces."""
    body = _bind(payload, ORDER_FIELDS)
    currency = body["currency"]
    if currency not in _CURRENCIES:
        raise ValidationError(f"unsupported currency: {currency}")
    ship = _bind(body["ship_to"], SHIP_FIELDS)
    lines_raw = body["lines"]
    if not isinstance(lines_raw, list) or not lines_raw:
        raise ValidationError("lines must be a non-empty list")
    lines = [_bind(item, LINE_FIELDS) for item in lines_raw]
    return {
        "customer_id": body["customer_id"],
        "currency": currency,
        "po_number": body["po_number"],
        "promised_on": body.get("promised_on"),
        "ship": ship,
        "lines": lines,
    }


def build_lines(parsed_lines: Sequence[Mapping[str, Any]]) -> list[LineItem]:
    """Construct line items from parsed line objects."""
    items: list[LineItem] = []
    for line in parsed_lines:
        items.append(
            LineItem(
                sku=str(line["sku"]),
                quantity=int(line["quantity"]),
                unit_price_cents=int(line["unit_price_cents"]),
            )
        )
    return items


def build_ship_to(parsed: Mapping[str, Any]) -> ShipTo:
    """Construct the destination from a parsed ship_to object."""
    raw_lines = parsed.get("lines") or []
    return ShipTo(
        region=str(parsed["region"]),
        city=str(parsed["city"]),
        lines=tuple(raw_lines),
    )


def _bind(payload: Mapping[str, Any], fields: Sequence[Field]) -> dict[str, Any]:
    """Copy declared fields and reject anything else."""
    if not isinstance(payload, Mapping):
        raise ValidationError("expected an object")
    known: set[str] = set()
    for field in fields:
        known.add(field.name)
        known.update(field.aliases)
        if field.aliases:
            known.update(payload)
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValidationError("unknown fields: " + ", ".join(unknown))
    bound: dict[str, Any] = {}
    for field in fields:
        present = _lookup(payload, field)
        if present is _MISSING:
            if field.required:
                raise ValidationError(f"{field.name} is required")
            continue
        bound[field.name] = _coerce(field, present)
    return bound


def _lookup(payload: Mapping[str, Any], field: Field) -> Any:
    """Resolve a field from its canonical name or a legacy alias."""
    found: list[Any] = []
    if field.name in payload:
        found.append(payload[field.name])
    for alias in field.aliases:
        if alias in payload:
            found.append(payload[alias])
    if not found:
        return _MISSING
    if any(item != found[0] for item in found[1:]):
        raise ValidationError(f"{field.name} conflicts with an alias")
    return found[0]


def _coerce(field: Field, value: Any) -> Any:
    """Apply the field kind and the numeric floor."""
    if field.kind == "str":
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{field.name} must be a non-empty string")
        return value.strip()
    if field.kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{field.name} must be an integer")
        if field.minimum is not None and value < field.minimum:
            raise ValidationError(f"{field.name} must be >= {field.minimum}")
        return value
    if field.kind == "date":
        return _coerce_date(field, value)
    if field.kind == "object":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field.name} must be an object")
        return value
    if field.kind == "list":
        if not isinstance(value, list):
            raise ValidationError(f"{field.name} must be a list")
        return value
    if field.kind == "str_list":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValidationError(f"{field.name} must be a list of strings")
        return value
    raise ValidationError(f"unsupported kind for {field.name}")


def _coerce_date(field: Field, value: Any) -> date:
    """Accept only a real calendar day written as YYYY-MM-DD."""
    if not isinstance(value, str):
        raise ValidationError(f"{field.name} must be a YYYY-MM-DD date")
    try:
        parsed = datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(f"{field.name} must be a YYYY-MM-DD date") from None
    return parsed
