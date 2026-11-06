from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from swiss_cheese_bench.fixtures import Category, Fixture, load_fixtures
from swiss_cheese_bench.scoring import (
    OVERALL,
    ScoringError,
    load_results,
    normalize_path,
    score_run,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURES = load_fixtures(ROOT)
DEFECTIVE = [f for f in FIXTURES if f.label.category is not Category.NONE]
CLEAN = [f for f in FIXTURES if f.label.category is Category.NONE]


def finding(cat: str, file: str | None) -> dict[str, Any]:
    return {"category": cat, "file": file, "line": None, "message": "m"}


def truth(f: Fixture) -> dict[str, Any]:
    return finding(str(f.label.category), f.label.file)


Behaviour = Callable[[Fixture, str], dict[str, Any]]


def row(f: Fixture, kind: str, **over: Any) -> dict[str, Any]:
    base = {
        "case_no": 1,
        "fixture_id": f.id,
        "kind": kind,
        "model_key": "A" if kind == "A" else "B",
        "status": "ok",
        "raw_text": None,
        "findings": [],
        "parse_ok": True,
        "invalid": 0,
        "input_tokens": 1,
        "output_tokens": 1,
        "cost_usd": 0.01 if kind != "B_after_A" else 0.02,
        "projected_cost_usd": 0.0,
        "error": None,
    }
    base.update(over)
    return base


def write_run(tmp: Path, behave: Behaviour, dry_run: bool = False, finalize: bool = True) -> Path:
    lines = []
    for f in FIXTURES:
        for kind in ("A", "B", "B_after_A"):
            r = row(f, kind, **behave(f, kind))
            if dry_run:
                r["cost_usd"] = 0.0
                if r["status"] == "ok":
                    r["status"] = "dry_run"
                    r["projected_cost_usd"] = 0.5
            lines.append(json.dumps(r))
    (tmp / "results.jsonl").write_text("\n".join(lines) + "\n")
    meta: dict[str, Any] = {"dry_run": dry_run, "cap_usd": 5.0, "models": {}}
    if finalize:
        meta["summary"] = {}
    (tmp / "run.json").write_text(json.dumps(meta))
    return tmp


def perfect(f: Fixture, kind: str) -> dict[str, Any]:
    return {"findings": [] if f.label.category is Category.NONE else [truth(f)]}


def test_perfect_reviewer(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, perfect), FIXTURES)
    assert len(s.cohort) == 24 and not s.excluded
    for name in ("A", "B", "A_then_B", "A_union_B"):
        cfg = s.configs[name]
        for cat, sc in cfg.categories.items():
            assert sc.precision == 1.0 and sc.recall == 1.0, (name, cat)
        assert cfg.overall.truth == 20 and cfg.overall.false_positives == 0
        assert cfg.recall_interval is not None and cfg.recall_interval[1] == 1.0
    assert s.blind_spots == []
    total = next(r for r in s.overlap if r.category == OVERALL)
    assert total.counts == {"both": 20, "A_only": 0, "B_only": 0, "neither": 0}
    assert total.a_then_b_caught["both"] == 20


def test_matching_rules(tmp_path: Path) -> None:
    sw = [f for f in DEFECTIVE if f.label.category is Category.SWALLOWED_ERROR]
    f0, f1, f2 = sw
    sec = next(f for f in DEFECTIVE if f.label.category is Category.SECRET_LOGGED)

    def behave(f: Fixture, kind: str) -> dict[str, Any]:
        if kind != "A":
            return {}
        cat = str(Category.SWALLOWED_ERROR)
        if f is f0:  # right category, wrong file => FP and miss
            return {"findings": [finding(cat, "other.py")]}
        if f is f1:  # duplicates + b/ prefix normalise to one correct finding
            return {"findings": [finding(cat, "b/" + str(f.label.file)), truth(f), truth(f)]}
        if f is f2:  # right file, wrong category => FP in wrong cat, miss here
            return {"findings": [finding("secret_logged", f.label.file)]}
        if f is sec:  # no file => never a catch
            return {"findings": [finding("secret_logged", None)]}
        if f is CLEAN[0]:  # finding on a clean control is an FP
            return {"findings": [finding(cat, "x.py")]}
        return {}

    s = score_run(write_run(tmp_path, behave), FIXTURES)
    a = s.configs["A"].categories
    assert (a["swallowed_error"].truth, a["swallowed_error"].tp) == (3, 1)
    # predicted: f0 wrong file (1) + f1 deduped (1) + clean control (1)
    assert a["swallowed_error"].predicted == 3
    assert a["swallowed_error"].precision == pytest.approx(1 / 3)
    assert a["swallowed_error"].recall == pytest.approx(1 / 3)
    # secret_logged: f2 wrong-category FP + sec no-file FP, no catches
    assert (a["secret_logged"].truth, a["secret_logged"].predicted, a["secret_logged"].tp) == (
        3,
        2,
        0,
    )
    assert a["secret_logged"].precision == 0.0
    # categories nobody predicted have undefined precision (None), not 0 or 1
    assert a["overbroad_iam"].predicted == 0 and a["overbroad_iam"].precision is None
    assert a["overbroad_iam"].recall == 0.0
    assert s.configs["A"].overall.truth == 20


def test_normalize_path() -> None:
    assert normalize_path("./b/x.py") == "x.py"
    assert normalize_path("a/x.py") == "x.py"
    assert normalize_path(" x.py ") == "x.py"


def test_failed_calls_unscored_and_cost_kept(tmp_path: Path) -> None:
    victim = DEFECTIVE[0]
    other = DEFECTIVE[1]

    def behave(f: Fixture, kind: str) -> dict[str, Any]:
        base = perfect(f, kind)
        if f is victim and kind == "B_after_A":
            return {"status": "error", "findings": [], "cost_usd": 0.5}
        if f is other and kind == "A":
            return {"status": "skipped_cost_cap", "findings": [], "cost_usd": 0.0}
        if f is other and kind == "B_after_A":
            return {"status": "skipped_dependency", "findings": [], "cost_usd": 0.0}
        return base

    s = score_run(write_run(tmp_path, behave), FIXTURES)
    assert set(s.excluded) == {victim.id, other.id}
    assert len(s.cohort) == 22
    assert s.configs["A"].overall.truth == 18  # cohort only
    # A_then_B cost on victim = A (0.01) + errored B_after_A (0.5): wasted money is not hidden
    base_total = 24 * 0.01 + 24 * 0.02
    expected = base_total - 0.02 + 0.5 - 0.01 - 0.02  # victim's error; other's A and B_after_A=0
    assert s.configs["A_then_B"].cost_incurred_usd == pytest.approx(expected)


def test_unparsable_is_a_miss_and_invalid_items_are_counted(tmp_path: Path) -> None:
    f_bad, f_inv = DEFECTIVE[0], DEFECTIVE[1]

    def behave(f: Fixture, kind: str) -> dict[str, Any]:
        if f is f_bad and kind == "A":
            return {"parse_ok": False, "findings": []}
        if f is f_inv and kind == "A":
            return {"invalid": 3, "findings": [truth(f)]}
        return perfect(f, kind)

    s = score_run(write_run(tmp_path, behave), FIXTURES)
    a = s.configs["A"]
    assert a.n_unparsable == 1 and a.n_invalid_items == 3
    assert a.overall.tp == 19 and a.overall.truth == 20
    assert s.configs["A_union_B"].overall.tp == 20  # B covers A's miss
    assert s.configs["A_union_B"].n_unparsable == 1


def test_overlap_buckets_rescue_and_costs(tmp_path: Path) -> None:
    a_only, b_only, neither = DEFECTIVE[0], DEFECTIVE[1], DEFECTIVE[2]
    both = DEFECTIVE[3:]

    def behave(f: Fixture, kind: str) -> dict[str, Any]:
        t = {"findings": [truth(f)]}
        if f in (a_only, neither) and kind == "B":
            return {"findings": []}
        if f in (b_only, neither) and kind == "A":
            return {"findings": []}
        if kind == "B_after_A":
            if f is neither:
                return {"findings": []}
            if f is b_only:
                return t  # sequential review rescues the B-only case
            if f is a_only:
                return {"findings": []}  # but loses the A-only case
        return t if f.label.category is not Category.NONE else {}

    s = score_run(write_run(tmp_path, behave), FIXTURES)
    total = next(r for r in s.overlap if r.category == OVERALL)
    assert total.counts == {"both": len(both), "A_only": 1, "B_only": 1, "neither": 1}
    assert total.a_then_b_caught == {"both": len(both), "A_only": 0, "B_only": 1, "neither": 0}
    assert s.blind_spots == [str(neither.label.category)]
    assert s.configs["A"].true_catches == 18 and s.configs["B"].true_catches == 18
    assert s.configs["A_union_B"].true_catches == 19  # both + A-only + B-only
    assert s.configs["A_then_B"].true_catches == 18  # both + rescued B-only, lost A-only
    # costs: A = 24 * 0.01; A_then_B = 24 * (0.01 + 0.02); union = A + B = 24 * 0.02
    assert s.configs["A"].cost_incurred_usd == pytest.approx(0.24)
    assert s.configs["A"].cost_per_true_catch == pytest.approx(0.24 / 18)
    assert s.configs["A_then_B"].cost_incurred_usd == pytest.approx(0.72)
    assert s.configs["A_union_B"].cost_incurred_usd == pytest.approx(0.48)
    # best single is A (tie => A, 18 catches, 0.24). Union: +1 catch for +0.24; A_then_B: +0.
    by = {m.config: m for m in s.marginal}
    assert by["A_union_B"].best_single == "A" and by["A_union_B"].extra_catches == 1
    assert by["A_union_B"].cost_per_extra_catch == pytest.approx(0.24)
    assert by["A_then_B"].extra_catches == 0 and by["A_then_B"].cost_per_extra_catch is None


def test_zero_catches_gives_none(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, lambda f, k: {}), FIXTURES)
    cfg = s.configs["A"]
    assert cfg.true_catches == 0 and cfg.cost_per_true_catch is None
    assert cfg.overall.precision is None and cfg.overall.recall == 0.0
    assert len(s.blind_spots) == 8


def test_dry_run_uses_projected_cost(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, perfect, dry_run=True), FIXTURES)
    assert s.dry_run
    assert s.configs["A"].cost_incurred_usd == pytest.approx(24 * 0.5)


def test_wilson_known_values() -> None:
    assert wilson_interval(0, 0) is None
    lo, hi = wilson_interval(10, 10) or (0, 0)
    assert lo == pytest.approx(0.7225, abs=1e-3) and hi == 1.0
    lo, hi = wilson_interval(0, 10) or (1, 1)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)


def _good_run(tmp: Path) -> Path:
    return write_run(tmp, perfect)


def _mutate_line(tmp: Path, idx: int, fn: Callable[[dict[str, Any]], None]) -> None:
    p = tmp / "results.jsonl"
    lines = p.read_text().splitlines()
    obj = json.loads(lines[idx])
    fn(obj)
    lines[idx] = json.dumps(obj)
    p.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda o: o.update(kind="Z"),
        lambda o: o.update(status="weird"),
        lambda o: o.update(fixture_id="nope"),
        lambda o: o.update(cost_usd=-1),
        lambda o: o.update(cost_usd=float("nan")),
        lambda o: o.update(cost_usd="1"),
        lambda o: o.update(findings="x"),
        lambda o: o.update(findings=[{"category": "bogus", "message": "m"}]),
        lambda o: o.update(parse_ok="yes"),
        lambda o: o.update(invalid=-1),
        lambda o: o.update(status="dry_run"),  # live run containing a dry-run row
    ],
)
def test_corrupt_rows_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], None]) -> None:
    _good_run(tmp_path)
    _mutate_line(tmp_path, 0, corrupt)
    with pytest.raises(ScoringError):
        load_results(tmp_path, FIXTURES)


def test_incomplete_and_interrupted_runs_rejected(tmp_path: Path) -> None:
    write_run(tmp_path, perfect, finalize=False)
    with pytest.raises(ScoringError, match="not finalized"):
        score_run(tmp_path, FIXTURES)
    _good_run(tmp_path)
    p = tmp_path / "results.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")  # truncated: one row missing
    with pytest.raises(ScoringError, match="incomplete"):
        score_run(tmp_path, FIXTURES)
    p.write_text("\n".join(lines + [lines[0]]) + "\n")  # duplicate
    with pytest.raises(ScoringError, match="duplicate"):
        score_run(tmp_path, FIXTURES)
    p.write_text("\n".join(lines[:-1] + ["{not json"]) + "\n")
    with pytest.raises(ScoringError, match="invalid JSON"):
        score_run(tmp_path, FIXTURES)


def test_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ScoringError):
        score_run(tmp_path, FIXTURES)


def test_scores_a_real_dry_run_end_to_end(tmp_path: Path) -> None:
    from swiss_cheese_bench.cli import main

    cfg = Path(__file__).resolve().parent.parent / "bench.example.json"
    out = tmp_path / "run"
    assert main(["run", "--config", str(cfg), "--out", str(out), "--dry-run"], env={}) == 0
    s = score_run(out, FIXTURES)
    assert s.dry_run and len(s.cohort) == 24
    assert s.configs["A"].cost_incurred_usd > 0
