"""Tier support: loader, hard-tier inventory/shape, run manifest, slices, CLI, report."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from swiss_cheese_bench.cli import main
from swiss_cheese_bench.fixtures import (
    DEFECT_CATEGORIES,
    Category,
    Fixture,
    FixtureError,
    load_fixtures,
    parse_diff,
)
from swiss_cheese_bench.report import render_report
from swiss_cheese_bench.scoring import (
    ScoringError,
    load_results,
    score_run,
    score_slices,
)
from tests.test_scoring import FIXTURES as EASY
from tests.test_scoring import perfect, write_run

ROOT = Path(__file__).resolve().parent.parent / "fixtures"
EXAMPLE = Path(__file__).resolve().parent.parent / "bench.example.json"
ALL = load_fixtures(ROOT)
HARD = [f for f in ALL if f.tier == "hard"]

HARD_DEFECTS = {
    "unrelated_deletion": ["go", "python", "python"],
    "dropped_requirement": ["go", "go", "python"],
    "test_bypasses_route": ["go", "go", "python"],
    "validation_disabled": ["go", "python", "python"],
    "hardcoded_expected": ["go", "go", "python"],
    "swallowed_error": ["go", "python", "python"],
    "secret_logged": ["go", "python", "terraform"],
    "overbroad_iam": ["terraform", "terraform", "terraform"],
}


def test_hard_inventory_is_exact() -> None:
    defective = [f for f in HARD if f.label.category is not Category.NONE]
    got: dict[str, list[str]] = {}
    for f in defective:
        got.setdefault(str(f.label.category), []).append(f.language)
    assert {k: sorted(v) for k, v in got.items()} == HARD_DEFECTS
    assert set(got) == {str(c) for c in DEFECT_CATEGORIES}
    clean = [f for f in HARD if f.label.category is Category.NONE]
    assert Counter(f.language for f in clean) == {"python": 3, "go": 3, "terraform": 2}
    assert Counter(f.language for f in defective) == {"python": 10, "go": 10, "terraform": 4}
    assert all(f.id.startswith("h_") for f in HARD) and len(HARD) == 32


def test_hard_diffs_have_the_documented_shape() -> None:
    for f in HARD:
        parsed = parse_diff(f.diff)
        files = [p for p in parsed.paths if parsed.added[p] or parsed.removed[p]]
        lines = sum(len(parsed.added[p]) + len(parsed.removed[p]) for p in files)
        assert 3 <= len(files) <= 6, (f.id, len(files))
        assert 100 <= lines <= 250, (f.id, lines)
        lowered = f.task.lower()
        assert not any(str(c) in lowered for c in DEFECT_CATEGORIES), f.id


def test_easy_fixtures_unchanged_and_default_tier() -> None:
    assert len(EASY) == 24 and all(f.tier == "easy" for f in EASY)


def _fixture_dir(tmp: Path, tier: object) -> Path:
    src = ROOT / "py_swallowed_error_1"
    dst = tmp / "py_swallowed_error_1"
    shutil.copytree(src, dst)
    label = json.loads((dst / "label.json").read_text())
    if tier is None:
        label.pop("tier", None)
    else:
        label["tier"] = tier
    (dst / "label.json").write_text(json.dumps(label))
    return tmp


def test_loader_tier_default_and_validation(tmp_path: Path) -> None:
    assert load_fixtures(_fixture_dir(tmp_path / "a", None))[0].tier == "easy"
    assert load_fixtures(_fixture_dir(tmp_path / "b", "hard"))[0].tier == "hard"
    with pytest.raises(FixtureError):
        load_fixtures(_fixture_dir(tmp_path / "c", "medium"))
    with pytest.raises(FixtureError):
        load_fixtures(_fixture_dir(tmp_path / "d", 3))


# ---- slices on synthetic hard clones of easy fixtures


def clones(tmp: Path, n: int = 6) -> list[Fixture]:
    out: list[Fixture] = []
    for src in EASY[:n]:
        new_id = "h_" + src.id
        dst = tmp / new_id
        shutil.copytree(ROOT / src.id, dst)
        meta = json.loads((dst / "meta.json").read_text())
        meta["id"] = new_id
        (dst / "meta.json").write_text(json.dumps(meta))
        label = json.loads((dst / "label.json").read_text())
        label["tier"] = "hard"
        (dst / "label.json").write_text(json.dumps(label))
    out = [f for f in load_fixtures(tmp) if f.tier == "hard"]
    assert len(out) == n
    return out


def mixed_fixtures(tmp: Path) -> list[Fixture]:
    return [*EASY, *clones(tmp)]


def test_legacy_run_without_manifest_is_easy_only(tmp_path: Path) -> None:
    fixtures = mixed_fixtures(tmp_path / "fx")
    run = write_run(tmp_path / "r", perfect, fixtures=EASY)
    s = score_run(run, fixtures)
    assert len(s.cohort) == 24
    assert list(score_slices(run, fixtures)) == ["easy"]


def test_manifest_slices_and_per_slice_costs(tmp_path: Path) -> None:
    fixtures = mixed_fixtures(tmp_path / "fx")
    hard_ids = {f.id for f in fixtures if f.tier == "hard"}

    def behave(f: Fixture, kind: str) -> dict[str, Any]:
        if f.id in hard_ids and kind == "A":
            return {"findings": [], "cost_usd": 1.0}  # A misses every hard defect
        return perfect(f, kind)

    run = write_run(tmp_path / "r", behave, fixtures=fixtures, manifest=True)
    slices = score_slices(run, fixtures)
    assert list(slices) == ["easy", "hard", "all"]
    assert slices["easy"].configs["A"].true_catches == 20
    hard_defects = sum(
        1 for f in fixtures if f.id in hard_ids and f.label.category is not Category.NONE
    )
    assert slices["hard"].configs["A"].true_catches == 0
    assert slices["hard"].configs["B"].true_catches == hard_defects
    assert slices["all"].configs["B"].true_catches == 20 + hard_defects
    # each slice sums only its own fixtures' calls; "all" is the sum of both
    a = {k: v.configs["A"].cost_incurred_usd for k, v in slices.items()}
    assert a["hard"] == pytest.approx(6 * 1.0)
    assert a["easy"] == pytest.approx(24 * 0.01)
    assert a["all"] == pytest.approx(a["easy"] + a["hard"])
    assert slices["hard"].blind_spots == []  # B caught everything A missed
    assert set(score_run(run, fixtures, "hard").cohort) == hard_ids


def test_manifest_mismatches_raise(tmp_path: Path) -> None:
    fixtures = mixed_fixtures(tmp_path / "fx")
    run = write_run(tmp_path / "r", perfect, fixtures=fixtures, manifest=True)
    with pytest.raises(ScoringError, match="not on disk"):
        load_results(run, EASY)  # manifest names hard fixtures that were not supplied
    with pytest.raises(ScoringError, match="tier 'hard'"):
        score_run(
            write_run(tmp_path / "r2", perfect, fixtures=EASY, manifest=True), fixtures, "hard"
        )
    # a row for an id outside the manifest is rejected
    meta = json.loads((run / "run.json").read_text())
    meta["manifest"] = meta["manifest"][:-1]
    (run / "run.json").write_text(json.dumps(meta))
    with pytest.raises(ScoringError, match="unknown fixture"):
        load_results(run, fixtures)
    meta["manifest"] = "nope"
    (run / "run.json").write_text(json.dumps(meta))
    with pytest.raises(ScoringError, match="manifest"):
        load_results(run, fixtures)


def test_report_renders_each_slice(tmp_path: Path) -> None:
    fixtures = mixed_fixtures(tmp_path / "fx")
    run = write_run(tmp_path / "r", perfect, fixtures=fixtures, manifest=True)
    md = render_report(score_slices(run, fixtures), "c.svg")
    assert (
        md.index("## Hard tier") < md.index("## Easy tier") < md.index("## All fixtures combined")
    )
    assert md.count("Blind spots (defects neither model caught)") == 3
    assert md.count("### Precision and recall by category") == 3
    assert "![Recall by defect category (hard tier)](c.svg)" in md


def test_cli_tier_flag_and_manifest_end_to_end(tmp_path: Path) -> None:
    out_easy = tmp_path / "easy"
    assert main(["run", "--config", str(EXAMPLE), "--out", str(out_easy), "--dry-run"], env={}) == 0
    meta = json.loads((out_easy / "run.json").read_text())
    assert meta["tier"] == "easy" and len(meta["manifest"]) == 24
    assert main(["report", "--run", str(out_easy), "--out", str(tmp_path / "e.md")]) == 0
    assert (
        main(["report", "--run", str(out_easy), "--out", str(tmp_path / "x.md"), "--tier", "hard"])
        == 2
    )
    if HARD:
        out_all = tmp_path / "all"
        cmd = ["run", "--config", str(EXAMPLE), "--out", str(out_all), "--dry-run", "--tier", "all"]
        assert main(cmd, env={}) == 0
        assert len(json.loads((out_all / "run.json").read_text())["manifest"]) == 24 + 32
        assert main(["report", "--run", str(out_all), "--out", str(tmp_path / "a.md")]) == 0
        assert "## Hard tier" in (tmp_path / "a.md").read_text()
    assert main(
        [
            "run",
            "--config",
            str(EXAMPLE),
            "--out",
            str(tmp_path / "none"),
            "--dry-run",
            "--tier",
            "hard",
        ],
        env={},
    ) == (0 if HARD else 2)
