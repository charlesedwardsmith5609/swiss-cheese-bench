from __future__ import annotations

from pathlib import Path

from swiss_cheese_bench.findings import Finding
from swiss_cheese_bench.fixtures import Category, load_fixtures
from swiss_cheese_bench.prompt import build_prompt

ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def test_prompt_has_task_and_diff_but_no_private_fixture_data() -> None:
    for f in load_fixtures(ROOT):
        p = build_prompt(f, 7)
        text = p.system + p.user
        assert f.task in p.user and f.diff in p.user
        assert "Case 7" in p.user
        assert f.id not in text
        if f.label.description:
            assert f.label.description not in text
        assert "Another reviewer" not in p.user


def test_prior_findings_only_when_given() -> None:
    f = load_fixtures(ROOT)[0]
    prior = [Finding(Category.SWALLOWED_ERROR, "a.py", 1, "ignored error")]
    assert "ignored error" in build_prompt(f, 1, prior).user
    assert "Another reviewer" in build_prompt(f, 1, []).user
