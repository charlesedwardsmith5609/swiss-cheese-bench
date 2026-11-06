"""Structured reviewer findings and a tolerant, never-raising JSON parser.

Threading: none; pure functions.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from swiss_cheese_bench.fixtures import Category

MAX_DECODE_FAILURES = 200


@dataclass(frozen=True)
class Finding:
    category: Category
    file: str | None
    line: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {
            "category": str(self.category),
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class ParseResult:
    findings: list[Finding] = field(default_factory=list)
    parse_ok: bool = False
    invalid: int = 0


def _candidates(text: str) -> Iterator[Any]:
    """JSON values found in text: the whole text first, then each fenced/embedded value."""
    try:
        yield json.loads(text)
        return
    except (ValueError, RecursionError):
        pass
    decoder = json.JSONDecoder()
    index = 0
    failures = 0
    while index < len(text) and failures < MAX_DECODE_FAILURES:
        if text[index] in "{[":
            try:
                value, end = decoder.raw_decode(text, index)
            except (ValueError, RecursionError):
                failures += 1  # bounds the work on adversarial input (no quadratic rescans)
                index += 1
                continue
            yield value
            index = end
        else:
            index += 1


def _one(item: object) -> Finding | None:
    if not isinstance(item, dict):
        return None
    raw_cat, message = item.get("category"), item.get("message")
    if not isinstance(raw_cat, str) or not isinstance(message, str) or not message.strip():
        return None
    try:
        category = Category(raw_cat)
    except ValueError:
        return None
    file, line = item.get("file"), item.get("line")
    if file is not None and not isinstance(file, str):
        return None
    if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
        return None
    return Finding(category, file, line, message.strip())


def parse_findings(text: str) -> ParseResult:
    """Parse reviewer output. Never raises.

    Accepts {"findings": [...]} or a bare list, bare or inside fences/prose. Items with an
    unknown category or wrong types are dropped and counted in `invalid`. Items with category
    "none" are ignored. Any other top-level shape gives parse_ok=False.
    """
    for value in _candidates(text):
        items = value.get("findings") if isinstance(value, dict) else value
        if not isinstance(items, list):
            continue
        result = ParseResult(parse_ok=True)
        for item in items:
            if isinstance(item, dict) and item.get("category") == "none":
                continue
            finding = _one(item)
            if finding is None:
                result.invalid += 1
            else:
                result.findings.append(finding)
        return result
    return ParseResult()
