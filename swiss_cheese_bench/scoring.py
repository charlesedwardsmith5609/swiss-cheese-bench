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

import hashlib
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
MAX_RESULTS_BYTES = 512 * 1024 * 1024


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
    manifest: tuple[str, ...] | None = None  # fixture ids run; None for legacy (easy-only) runs


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
class Claim:
    """One non-seeded finding. id is `<fixture>/<kind>/<index>`; file may be None."""

    id: str
    fixture_id: str
    kind: str
    category: Category
    file: str | None
    message: str


@dataclass(frozen=True)
class Adjudication:
    adjudicator: str
    verdicts: dict[str, str]  # claim id -> real | not_real | unclear


@dataclass(frozen=True)
class ExtraCounts:
    """Distinct extra findings (clusters) of one config by adjudicated verdict."""

    real: int
    not_real: int
    unclear: int

    @property
    def total(self) -> int:
        return self.real + self.not_real + self.unclear


@dataclass(frozen=True)
class ExtrasOverlap:
    """Distinct extras raised by A and/or B on the fixtures both scored."""

    fixtures: int
    real_a_only: int
    real_b_only: int
    real_both: int
    all_a_only: int
    all_b_only: int
    all_both: int


@dataclass(frozen=True)
class ConfigScore:
    name: str
    categories: dict[str, CategoryScore]  # defect categories + OVERALL
    n_unparsable: int
    n_invalid_items: int
    cost_incurred_usd: float
    recall_interval: tuple[float, float] | None
    extras: ExtraCounts | None = None  # None when the run has no adjudication

    @property
    def overall(self) -> CategoryScore:
        return self.categories[OVERALL]

    @property
    def true_catches(self) -> int:
        return self.overall.tp

    @property
    def adjusted_precision(self) -> float | None:
        """Precision counting adjudicated-real extras as correct (needs an adjudication)."""
        if self.extras is None or not self.overall.predicted:
            return None
        return (self.overall.tp + self.extras.real) / self.overall.predicted

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
    adjudicator: str | None = None
    extras_overlap: ExtrasOverlap | None = None

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
    if not parse_ok and findings_raw:
        raise ScoringError(f"{where}: unparsable output cannot carry findings")
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


def resolve_run_fixtures(meta: RunMeta, fixtures: list[Fixture]) -> list[Fixture]:
    """The fixtures a run covered: its manifest, or (legacy runs) the easy tier."""
    if meta.manifest is None:
        return [f for f in fixtures if f.tier == "easy"]
    by_id = {f.id: f for f in fixtures}
    missing = [i for i in meta.manifest if i not in by_id]
    if missing:
        raise ScoringError(f"run manifest names fixtures not on disk, e.g. {missing[0]!r}")
    return [by_id[i] for i in sorted(set(meta.manifest))]


def load_results(run_dir: Path, fixtures: list[Fixture]) -> tuple[RunMeta, list[CallRow]]:
    try:
        meta_raw = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        results_path = run_dir / "results.jsonl"
        if results_path.stat().st_size > MAX_RESULTS_BYTES:
            raise ScoringError(f"results.jsonl exceeds {MAX_RESULTS_BYTES} bytes")
        lines = results_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoringError(f"cannot read run in {run_dir}: {exc}") from exc
    if not isinstance(meta_raw, dict) or not isinstance(meta_raw.get("dry_run"), bool):
        raise ScoringError("run.json: dry_run must be a boolean")
    summary, models = meta_raw.get("summary"), meta_raw.get("models")
    if not isinstance(summary, dict):
        raise ScoringError("run.json has no summary: the run was interrupted or is not finalized")
    if not isinstance(models, dict):
        raise ScoringError("run.json: models must be an object")
    manifest_raw = meta_raw.get("manifest")
    manifest: tuple[str, ...] | None = None
    if manifest_raw is not None:
        if not isinstance(manifest_raw, list) or not all(isinstance(x, str) for x in manifest_raw):
            raise ScoringError("run.json: manifest must be a list of fixture ids")
        manifest = tuple(manifest_raw)
    meta = RunMeta(
        meta_raw["dry_run"], _num(meta_raw.get("cap_usd"), "cap_usd"), models, summary, manifest
    )
    fixtures = resolve_run_fixtures(meta, fixtures)
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


def score_run(run_dir: Path, fixtures: list[Fixture], tier: str | None = None) -> Scoring:
    """Score one slice: the given tier, or every fixture the run covered when tier is None."""
    meta, rows = load_results(run_dir, fixtures)
    fixtures = resolve_run_fixtures(meta, fixtures)
    run_claims = claims_from_rows(rows, fixtures)
    adjudication = load_adjudication(run_dir, run_claims)
    if tier is not None:
        fixtures = [f for f in fixtures if f.tier == tier]
        if not fixtures:
            raise ScoringError(f"the run has no fixtures in tier {tier!r}")
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
    if adjudication is not None:
        scored = {c: {f.id for f in fixtures if outcomes[c][f.id].scored} for c in CONFIGS}
        result = apply_adjudication(result, run_claims, adjudication, scored)
    return result


def score_slices(run_dir: Path, fixtures: list[Fixture]) -> dict[str, Scoring]:
    """Complete scorings for each tier the run covered, plus "all" when more than one."""
    meta, _rows = load_results(run_dir, fixtures)
    covered = resolve_run_fixtures(meta, fixtures)
    tiers = [t for t in ("easy", "hard") if any(f.tier == t for f in covered)]
    slices = {t: score_run(run_dir, fixtures, t) for t in tiers}
    if len(tiers) > 1:
        slices["all"] = score_run(run_dir, fixtures)
    return slices


# ------------------------------------------------------------------ extra findings (R6)

VERDICTS = frozenset({"real", "not_real", "unclear"})


def results_fingerprint(run_dir: Path) -> str:
    try:
        return hashlib.sha256((run_dir / "results.jsonl").read_bytes()).hexdigest()
    except OSError as exc:
        raise ScoringError(f"cannot read results.jsonl: {exc}") from exc


def claims_from_rows(rows: list[CallRow], fixtures: list[Fixture]) -> list[Claim]:
    """Every finding that is not the seeded catch, from scored calls (parse_ok), in row order."""
    labels = {f.id: f.label for f in fixtures}
    claims: list[Claim] = []
    for row in rows:
        if row.status not in SCORED_STATUSES or row.fixture_id not in labels:
            continue
        label = labels[row.fixture_id]
        for index, finding in enumerate(row.findings):
            file = normalize_path(finding.file) if finding.file else None
            if (
                label.category is not Category.NONE
                and finding.category == label.category
                and file == label.file
            ):
                continue
            claims.append(
                Claim(
                    f"{row.fixture_id}/{row.kind}/{index}",
                    row.fixture_id,
                    row.kind,
                    finding.category,
                    file,
                    finding.message,
                )
            )
    return claims


def load_adjudication(run_dir: Path, claims: list[Claim]) -> Adjudication | None:
    """None when absent. A present file must match the results and cover every claim exactly."""
    path = run_dir / "adjudication.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoringError(f"cannot read adjudication.json: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("adjudicator"), str):
        raise ScoringError("adjudication.json: adjudicator must be a string")
    if data.get("fingerprint") != results_fingerprint(run_dir):
        raise ScoringError("adjudication.json does not match results.jsonl (stale fingerprint)")
    items = data.get("items")
    if not isinstance(items, list):
        raise ScoringError("adjudication.json: items must be a list")
    verdicts: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ScoringError("adjudication.json: each item must be an object")
        claim_id, verdict = item.get("claim_id"), item.get("verdict")
        if not isinstance(claim_id, str) or verdict not in VERDICTS:
            raise ScoringError("adjudication.json: bad claim_id or verdict")
        if claim_id in verdicts:
            raise ScoringError(f"adjudication.json: duplicate claim {claim_id!r}")
        verdicts[claim_id] = str(verdict)
    expected = {c.id for c in claims}
    if set(verdicts) != expected:
        missing, extra = len(expected - set(verdicts)), len(set(verdicts) - expected)
        raise ScoringError(
            f"adjudication.json does not cover the run's claims exactly "
            f"({missing} missing, {extra} unknown)"
        )
    return Adjudication(data["adjudicator"], verdicts)


def _cluster_verdict(verdicts: list[str]) -> str:
    if all(v == "real" for v in verdicts):
        return "real"
    if all(v == "not_real" for v in verdicts):
        return "not_real"
    return "unclear"


def _clusters(
    claims: list[Claim], adj: Adjudication, kinds: tuple[str, ...], fixture_ids: set[str]
) -> dict[tuple[str, Category, str | None], str]:
    grouped: dict[tuple[str, Category, str | None], list[str]] = {}
    for claim in claims:
        if claim.kind in kinds and claim.fixture_id in fixture_ids:
            key = (claim.fixture_id, claim.category, claim.file)
            grouped.setdefault(key, []).append(adj.verdicts[claim.id])
    return {key: _cluster_verdict(v) for key, v in grouped.items()}


def apply_adjudication(
    result: Scoring, claims: list[Claim], adj: Adjudication, scored_by_config: dict[str, set[str]]
) -> Scoring:
    """Attach per-config extra counts and the A-vs-B extras overlap to a scored slice."""
    from dataclasses import replace

    new_configs: dict[str, ConfigScore] = {}
    for name, cfg in result.configs.items():
        clusters = _clusters(claims, adj, SOURCES[name], scored_by_config[name])
        counts = [v for v in clusters.values()]
        new_configs[name] = replace(
            cfg,
            extras=ExtraCounts(
                counts.count("real"), counts.count("not_real"), counts.count("unclear")
            ),
        )
    both_scored = scored_by_config["A"] & scored_by_config["B"]
    a_clusters = _clusters(claims, adj, ("A",), both_scored)
    b_clusters = _clusters(claims, adj, ("B",), both_scored)
    merged: dict[tuple[str, Category, str | None], tuple[bool, bool, str]] = {}
    for key in set(a_clusters) | set(b_clusters):
        in_a, in_b = key in a_clusters, key in b_clusters
        verdict = _cluster_verdict([v for v in (a_clusters.get(key), b_clusters.get(key)) if v])
        merged[key] = (in_a, in_b, verdict)

    def count(only: str, real_only: bool) -> int:
        return sum(
            1
            for in_a, in_b, verdict in merged.values()
            if (not real_only or verdict == "real")
            and (
                (only == "a" and in_a and not in_b)
                or (only == "b" and in_b and not in_a)
                or (only == "both" and in_a and in_b)
            )
        )

    result.configs = new_configs
    result.adjudicator = adj.adjudicator
    result.extras_overlap = ExtrasOverlap(
        len(both_scored),
        count("a", True),
        count("b", True),
        count("both", True),
        count("a", False),
        count("b", False),
        count("both", False),
    )
    return result
