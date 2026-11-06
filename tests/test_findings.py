from __future__ import annotations

import pytest

from swiss_cheese_bench.findings import parse_findings
from swiss_cheese_bench.fixtures import Category

ITEM = '{"category": "swallowed_error", "file": "a.py", "line": 3, "message": "ignored"}'


def test_plain_object() -> None:
    res = parse_findings('{"findings": [' + ITEM + "]}")
    assert res.parse_ok and res.invalid == 0
    assert res.findings[0].category is Category.SWALLOWED_ERROR
    assert res.findings[0].line == 3


def test_fenced_and_prose_wrapped_and_bare_list() -> None:
    assert len(parse_findings('```json\n{"findings": [' + ITEM + "]}\n```").findings) == 1
    assert len(parse_findings('Here you go: {"findings": [' + ITEM + "]} thanks").findings) == 1
    assert len(parse_findings("[" + ITEM + "]").findings) == 1


def test_empty_list_is_valid_clean_review() -> None:
    res = parse_findings('{"findings": []}')
    assert res.parse_ok and not res.findings


def test_bad_items_counted_and_none_ignored() -> None:
    text = (
        '{"findings": [' + ITEM + ', {"category": "bogus", "message": "x"},'
        ' {"category": "swallowed_error"}, "str", {"category": "none", "message": "fine"},'
        ' {"category": "swallowed_error", "message": "m", "line": true}]}'
    )
    res = parse_findings(text)
    assert res.parse_ok
    assert len(res.findings) == 1
    assert res.invalid == 4


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no json here",
        "42",
        '"x"',
        '{"findings": "invalid"}',
        '{"other": []}',
        "{broken",
        "null",
    ],
)
def test_unsupported_shapes_are_not_ok(text: str) -> None:
    res = parse_findings(text)
    assert not res.parse_ok and not res.findings


def test_deeply_nested_input_does_not_raise() -> None:
    assert not parse_findings("[" * 100000).parse_ok


def test_huge_integer_digits_do_not_raise() -> None:
    assert not parse_findings("[" + "9" * 100000 + "]").parse_ok
    assert not parse_findings('prefix {"findings": [' + "9" * 100000 + "]}").parse_ok
