"""Fixture format, loader and ground-truth consistency tests (no network)."""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from swiss_cheese_bench.fixtures import (
    DEFECT_CATEGORIES,
    Category,
    FixtureError,
    load_fixtures,
    make_diff,
    parse_diff,
)

ROOT = Path(__file__).resolve().parent.parent / "fixtures"

EXPECTED_DEFECTS = {
    "unrelated_deletion": ["go", "python"],
    "dropped_requirement": ["go", "go", "python"],
    "test_bypasses_route": ["go", "python"],
    "validation_disabled": ["go", "python"],
    "hardcoded_expected": ["go", "go", "python"],
    "swallowed_error": ["go", "python", "python"],
    "secret_logged": ["go", "python", "terraform"],
    "overbroad_iam": ["terraform", "terraform"],
}
EXPECTED_CLEAN = ["go", "go", "python", "terraform"]


def test_all_fixtures_load_and_ids_match_dirs() -> None:
    fixtures = load_fixtures(ROOT)
    assert [f.id for f in fixtures] == sorted(p.name for p in ROOT.iterdir() if p.is_dir())
    assert len({f.id for f in fixtures}) == len(fixtures)


def test_inventory_counts_are_exact() -> None:
    fixtures = [f for f in load_fixtures(ROOT) if f.tier == "easy"]
    got: dict[str, list[str]] = {}
    clean: list[str] = []
    for f in fixtures:
        if f.label.category is Category.NONE:
            clean.append(f.language)
        else:
            got.setdefault(str(f.label.category), []).append(f.language)
    assert {k: sorted(v) for k, v in got.items()} == EXPECTED_DEFECTS
    assert sorted(clean) == EXPECTED_CLEAN
    assert sum(len(v) for v in got.values()) == 20
    assert set(got) == {str(c) for c in DEFECT_CATEGORIES}
    langs = Counter(lang for v in got.values() for lang in v)
    assert langs == {"python": 8, "go": 9, "terraform": 3}


def test_committed_diff_matches_regenerated() -> None:
    for f in load_fixtures(ROOT):
        assert make_diff(f.base_dir, f.after_dir) == f.diff, f.id


def test_diff_applies_to_base_and_reproduces_after() -> None:
    for f in load_fixtures(ROOT):
        with tempfile.TemporaryDirectory(prefix="scb-apply-") as tmp:
            work = Path(tmp) / "w"
            shutil.copytree(f.base_dir, work)
            patch = Path(tmp) / "d.patch"
            patch.write_text(f.diff, encoding="utf-8", newline="\n")
            res = subprocess.run(  # noqa: S603
                ["git", "apply", "--unsafe-paths", str(patch)],  # noqa: S607
                cwd=work,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert res.returncode == 0, f"{f.id}: {res.stderr}"
            for after_file in f.after_dir.rglob("*"):
                if after_file.is_file():
                    rel = after_file.relative_to(f.after_dir)
                    assert (work / rel).read_bytes() == after_file.read_bytes(), (f.id, rel)
            before = {p.relative_to(work) for p in work.rglob("*") if p.is_file()}
            after = {p.relative_to(f.after_dir) for p in f.after_dir.rglob("*") if p.is_file()}
            assert before == after, f.id


def test_reviewer_visible_meta_does_not_leak_ground_truth() -> None:
    for f in load_fixtures(ROOT):
        # Only the task text is reviewer-visible. (Fixture ids contain the category name, so the
        # runner must never put the id in a prompt; tests/test_prompt covers that later.)
        meta = f.task.lower()
        for cat in DEFECT_CATEGORIES:
            assert str(cat) not in meta, f.id
        if f.label.description:
            assert f.label.description.lower() not in meta


def test_parse_diff_ignores_headers() -> None:
    text = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n"
        " keep\n-old line\n+new line\n"
    )
    parsed = parse_diff(text)
    assert parsed.paths == {"x.py"}
    assert parsed.added["x.py"] == ["new line"]
    assert parsed.removed["x.py"] == ["old line"]


def _write_fixture(
    root: Path, *, label: dict[str, object] | str, meta: dict[str, object] | None = None
) -> Path:
    d = root / "fx"
    (d / "base").mkdir(parents=True)
    (d / "after").mkdir()
    (d / "base" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (d / "after" / "a.py").write_text("x = 2\n", encoding="utf-8")
    (d / "diff.patch").write_text(make_diff(d / "base", d / "after"), encoding="utf-8")
    m = meta if meta is not None else {"id": "fx", "language": "python", "task": "t"}
    (d / "meta.json").write_text(json.dumps(m), encoding="utf-8")
    text = label if isinstance(label, str) else json.dumps(label)
    (d / "label.json").write_text(text, encoding="utf-8")
    return root


GOOD_LABEL: dict[str, object] = {
    "category": "swallowed_error",
    "file": "a.py",
    "description": "d",
    "evidence": "x = 2",
}


def test_good_synthetic_fixture_loads(tmp_path: Path) -> None:
    assert len(load_fixtures(_write_fixture(tmp_path, label=GOOD_LABEL))) == 1


@pytest.mark.parametrize(
    "label",
    [
        "{not json",
        {"category": "bogus", "file": "a.py", "description": "d", "evidence": "x = 2"},
        {"category": 5},
        {**GOOD_LABEL, "evidence": "--- a/a.py"},
        {**GOOD_LABEL, "evidence": "absent"},
        {**GOOD_LABEL, "file": "other.py"},
        {"category": "none", "file": "a.py"},
        {"category": "swallowed_error"},
    ],
)
def test_bad_labels_raise_fixture_error(tmp_path: Path, label: dict[str, object] | str) -> None:
    with pytest.raises(FixtureError):
        load_fixtures(_write_fixture(tmp_path, label=label))


def test_clean_control_loads(tmp_path: Path) -> None:
    assert load_fixtures(_write_fixture(tmp_path, label={"category": "none"}))[0].label.file is None


def test_missing_and_bad_meta_raise_fixture_error(tmp_path: Path) -> None:
    root = _write_fixture(tmp_path, label=GOOD_LABEL)
    (root / "fx" / "meta.json").unlink()
    with pytest.raises(FixtureError):
        load_fixtures(root)
    (root / "fx" / "meta.json").write_bytes(b"\xff\xfe")
    with pytest.raises(FixtureError):
        load_fixtures(root)
    (root / "fx" / "meta.json").write_text('{"id": "fx", "language": 3, "task": "t"}')
    with pytest.raises(FixtureError):
        load_fixtures(root)
    (root / "fx" / "meta.json").write_text('{"id": "zz", "language": "python", "task": "t"}')
    with pytest.raises(FixtureError):
        load_fixtures(root)
    (root / "fx" / "meta.json").write_text('{"id": "fx", "language": "cobol", "task": "t"}')
    with pytest.raises(FixtureError):
        load_fixtures(root)


def test_oversized_diff_rejected(tmp_path: Path) -> None:
    root = _write_fixture(tmp_path, label=GOOD_LABEL)
    (root / "fx" / "diff.patch").write_text("x" * (300 * 1024), encoding="utf-8")
    with pytest.raises(FixtureError, match="exceeds"):
        load_fixtures(root)


def test_oversized_meta_rejected(tmp_path: Path) -> None:
    root = _write_fixture(tmp_path, label=GOOD_LABEL)
    big = {"id": "fx", "language": "python", "task": "t" * (300 * 1024)}
    (root / "fx" / "meta.json").write_text(json.dumps(big), encoding="utf-8")
    with pytest.raises(FixtureError, match="exceeds"):
        load_fixtures(root)
