"""Scoring: precision/recall per category, A-vs-B overlap, and cost per true catch.

Threading: none. Pure, synchronous functions over `<run>/results.jsonl` and fixture labels;
nothing is written and there is no shared state.

Reviewer configs are derived from the recorded calls (A, B, B_after_A):
  A          = call A
  B          = call B
  A_then_B   = call B_after_A (B sees A's findings and gives the final list); cost A + B_after_A
  A_union_B  = independent A and B findings merged (no extra calls); cost A + B
All comparative numbers use a common cohort: the fixtures for which every config is scored.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from swiss_cheese_bench.findings import Finding
from swiss_cheese_bench.fixtures import DEFECT_CATEGORIES, Category, Fixture

CONFIGS = ("A", "B", "A_then_B", "A_union_B")
REQUIRED = {
    "A": ("A",),
    "B": ("B",),
    "A_then_B": ("A", "B_after_A"),
    "A_union_B": ("A", "B"),
}
SOURCES = {
    "A": ("A",),
    "B": ("B",),
    "A_then_B": ("B_after_A",),
    "A_union_B": ("A", "B"),
}
KINDS = ("A", "B", "B_after_A")
STATUSES = frozenset({"ok", "error", "skipped_cost_cap", "skipped_dependency", "dry_run"})
SCORED_STATUSES = frozenset({"ok", "dry_run"})
BUCKETS = ("both", "A_only", "B_only", "neither")
OVERALL = "overall"


class ScoringError(Exception):
    """The run directory is malformed, incomplete, or inconsistent with the fixtures."""


@dataclass(frozen=True)
class CallRow:
    fixture_id: str
    kind: str
    status: str
    findings: tuple[Finding, ...]
    parse_ok: bool
    invalid: int
    cost_usd: float
    projected_cost_usd: float


@dataclass(frozen=True)
class RunMeta:
    dry_run: bool
    cap_usd: float
    models: dict[str, dict[str, object]]
    summary: dict[str, object]


@dataclass(frozen=True)
class CategoryScore:
    truth: int
    predicted: int
    tp: int

    @property
    def precision(self) -> float | None:
        return self.tp / self.predicted if self.predicted else None

    @property
    def recall(self) -> float | None:
        return self.tp / self.truth if self.truth else None

    @property
    def false_positives(self) -> int:
        return self.predicted - self.tp


@dataclass(frozen=True)
class ConfigScore:
    name: str
    categories: dict[str, CategoryScore]  # defect categories + OVERALL
    n_unparsable: int
    n_invalid_items: int
    cost_incurred_usd: float
    recall_interval: tuple[float, float] | None

    @property
    def overall(self) -> CategoryScore:
        return self.categories[OVERALL]

    @property
    def true_catches(self) -> int:
        return self.overall.tp

    @property
    def cost_per_true_catch(self) -> float | None:
        return self.cost_incurred_usd / self.true_catches if self.true_catches else None


@dataclass(frozen=True)
class OverlapRow:
    category: str
    counts: dict[str, int]  # BUCKETS -> count
    a_then_b_caught: dict[str, int]  # BUCKETS -> how many A_then_B caught (denominator = counts)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True)
class Marginal:
    config: str
    best_single: str
    extra_catches: int
    extra_cost_usd: float
    cost_per_extra_catch: float | None


@dataclass
class Scoring:
    meta: RunMeta
    cohort: list[str]
    excluded: dict[str, str] = field(default_factory=dict)
    configs: dict[str, ConfigScore] = field(default_factory=dict)
    overlap: list[OverlapRow] = field(default_factory=list)  # defect categories, then OVERALL
    marginal: list[Marginal] = field(default_factory=list)

    @property
    def dry_run(self) -> bool:
        return self.meta.dry_run

    @property
    def blind_spots(self) -> list[str]:
        return [r.category for r in self.overlap if r.category != OVERALL and r.counts["neither"]]


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def normalize_path(path: str) -> str:
    out = path.strip()
    while out.startswith("./"):
        out = out[2:]
    if out[:2] in ("a/", "b/"):
        out = out[2:]
    return out


# ------------------------------------------------------------------ loading


def _num(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ScoringError(f"{what} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ScoringError(f"{what} must be finite and >= 0")
    return number


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScoringError(f"{what} must be a non-negative integer")
    return value


def _finding(item: object, where: str) -> Finding:
    if not isinstance(item, dict):
        raise ScoringError(f"{where}: finding must be an object")
    try:
        category = Category(item["category"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ScoringError(f"{where}: bad finding category") from exc
    file, line, message = item.get("file"), item.get("line"), item.get("message")
    if file is not None and not isinstance(file, str):
        raise ScoringError(f"{where}: finding file must be a string or null")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int)):
        raise ScoringError(f"{where}: finding line must be an int or null")
    if not isinstance(message, str):
        raise ScoringError(f"{where}: finding message must be a string")
    return Finding(category, file, line, message)


def _row(raw: object, lineno: int, dry_run: bool) -> CallRow:
    where = f"results.jsonl line {lineno}"
    if not isinstance(raw, dict):
        raise ScoringError(f"{where}: row must be an object")
    fixture_id, kind, status = raw.get("fixture_id"), raw.get("kind"), raw.get("status")
    if not isinstance(fixture_id, str):
        raise ScoringError(f"{where}: fixture_id must be a string")
    if kind not in KINDS:
        raise ScoringError(f"{where}: unknown kind {kind!r}")
    if status not in STATUSES:
        raise ScoringError(f"{where}: unknown status {status!r}")
    if (status == "dry_run") != (dry_run and status in SCORED_STATUSES):
        raise ScoringError(f"{where}: status {status!r} inconsistent with run dry_run={dry_run}")
    findings_raw = raw.get("findings")
    if not isinstance(findings_raw, list):
        raise ScoringError(f"{where}: findings must be a list")
    parse_ok = raw.get("parse_ok")
    if not isinstance(parse_ok, bool):
        raise ScoringError(f"{where}: parse_ok must be a boolean")
    cost, projected = (
        _num(raw.get("cost_usd"), f"{where}: cost_usd"),
        _num(raw.get("projected_cost_usd"), f"{where}: projected_cost_usd"),
    )
    if dry_run and cost != 0:
        raise ScoringError(f"{where}: dry-run row has non-zero cost_usd")
    return CallRow(
        fixture_id,
        str(kind),
        str(status),
        tuple(_finding(f, where) for f in findings_raw),
        parse_ok,
        _count(raw.get("invalid"), f"{where}: invalid"),
        cost,
        projected,
    )


def load_results(run_dir: Path, fixtures: list[Fixture]) -> tuple[RunMeta, list[CallRow]]:
    try:
        meta_raw = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        lines = (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoringError(f"cannot read run in {run_dir}: {exc}") from exc
    if not isinstance(meta_raw, dict) or not isinstance(meta_raw.get("dry_run"), bool):
        raise ScoringError("run.json: dry_run must be a boolean")
    summary, models = meta_raw.get("summary"), meta_raw.get("models")
    if not isinstance(summary, dict):
        raise ScoringError("run.json has no summary: the run was interrupted or is not finalized")
    if not isinstance(models, dict):
        raise ScoringError("run.json: models must be an object")
    meta = RunMeta(meta_raw["dry_run"], _num(meta_raw.get("cap_usd"), "cap_usd"), models, summary)
    known = {f.id for f in fixtures}
    rows: list[CallRow] = []
    seen: set[tuple[str, str]] = set()
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScoringError(f"results.jsonl line {lineno}: invalid JSON") from exc
        row = _row(raw, lineno, meta.dry_run)
        if row.fixture_id not in known:
            raise ScoringError(f"results.jsonl line {lineno}: unknown fixture {row.fixture_id!r}")
        if (row.fixture_id, row.kind) in seen:
            raise ScoringError(f"results.jsonl line {lineno}: duplicate row")
        seen.add((row.fixture_id, row.kind))
        rows.append(row)
    missing = [(f.id, k) for f in fixtures for k in KINDS if (f.id, k) not in seen]
    if missing:
        raise ScoringError(
            f"results.jsonl is incomplete: {len(missing)} rows missing, e.g. {missing[0]}"
        )
    return meta, rows


# ------------------------------------------------------------------ scoring


@dataclass(frozen=True)
class _Outcome:
    scored: bool
    found: frozenset[tuple[Category, str | None]]
    unparsable: bool
    invalid: int
    cost: float


def _outcome(config: str, calls: dict[str, CallRow], dry_run: bool) -> _Outcome:
    required = [calls[k] for k in REQUIRED[config]]
    cost = sum(c.projected_cost_usd if dry_run else c.cost_usd for c in required)
    if not all(c.status in SCORED_STATUSES for c in required):
        return _Outcome(False, frozenset(), False, 0, cost)
    sources = [calls[k] for k in SOURCES[config]]
    found = frozenset(
        (f.category, normalize_path(f.file) if f.file else None)
        for c in sources
        for f in c.findings
    )
    return _Outcome(
        True,
        found,
        any(not c.parse_ok for c in sources),
        sum(c.invalid for c in sources),
        cost,
    )


def _correct(fixture: Fixture, found: frozenset[tuple[Category, str | None]]) -> bool:
    label = fixture.label
    return label.category is not Category.NONE and (label.category, label.file) in found


def score_run(run_dir: Path, fixtures: list[Fixture]) -> Scoring:
    meta, rows = load_results(run_dir, fixtures)
    by_fixture: dict[str, dict[str, CallRow]] = {}
    for row in rows:
        by_fixture.setdefault(row.fixture_id, {})[row.kind] = row
    outcomes: dict[str, dict[str, _Outcome]] = {
        c: {f.id: _outcome(c, by_fixture[f.id], meta.dry_run) for f in fixtures} for c in CONFIGS
    }
    cohort_fixtures = [f for f in fixtures if all(outcomes[c][f.id].scored for c in CONFIGS)]
    result = Scoring(meta=meta, cohort=[f.id for f in cohort_fixtures])
    for f in fixtures:
        bad = [c for c in CONFIGS if not outcomes[c][f.id].scored]
        if bad:
            result.excluded[f.id] = "unscored: " + ", ".join(bad)

    caught: dict[str, dict[str, bool]] = {c: {} for c in CONFIGS}
    for c in CONFIGS:
        truth = dict.fromkeys(DEFECT_CATEGORIES, 0)
        predicted = dict.fromkeys(DEFECT_CATEGORIES, 0)
        tp = dict.fromkeys(DEFECT_CATEGORIES, 0)
        unparsable = invalid = 0
        for f in cohort_fixtures:
            out = outcomes[c][f.id]
            unparsable += out.unparsable
            invalid += out.invalid
            for cat, _file in out.found:
                if cat is not Category.NONE:
                    predicted[cat] += 1
            hit = _correct(f, out.found)
            caught[c][f.id] = hit
            if f.label.category is not Category.NONE:
                truth[f.label.category] += 1
                tp[f.label.category] += hit
        cats = {str(k): CategoryScore(truth[k], predicted[k], tp[k]) for k in DEFECT_CATEGORIES}
        cats[OVERALL] = CategoryScore(
            sum(truth.values()), sum(predicted.values()), sum(tp.values())
        )
        result.configs[c] = ConfigScore(
            name=c,
            categories=cats,
            n_unparsable=unparsable,
            n_invalid_items=invalid,
            cost_incurred_usd=sum(o.cost for o in outcomes[c].values()),
            recall_interval=wilson_interval(cats[OVERALL].tp, cats[OVERALL].truth),
        )

    rows_by_cat: dict[str, OverlapRow] = {}
    for name in [str(k) for k in DEFECT_CATEGORIES] + [OVERALL]:
        rows_by_cat[name] = OverlapRow(name, dict.fromkeys(BUCKETS, 0), dict.fromkeys(BUCKETS, 0))
    for f in cohort_fixtures:
        if f.label.category is Category.NONE:
            continue
        a, b = caught["A"][f.id], caught["B"][f.id]
        bucket = "both" if a and b else "A_only" if a else "B_only" if b else "neither"
        for name in (str(f.label.category), OVERALL):
            rows_by_cat[name].counts[bucket] += 1
            rows_by_cat[name].a_then_b_caught[bucket] += caught["A_then_B"][f.id]
    result.overlap = list(rows_by_cat.values())

    single = {c: result.configs[c] for c in ("A", "B")}
    best = max(single, key=lambda c: (single[c].true_catches, c == "A"))
    for pair in ("A_then_B", "A_union_B"):
        extra = result.configs[pair].true_catches - single[best].true_catches
        extra_cost = result.configs[pair].cost_incurred_usd - single[best].cost_incurred_usd
        result.marginal.append(
            Marginal(pair, best, extra, extra_cost, extra_cost / extra if extra > 0 else None)
        )
    return result
