"""Benchmark runner: sends each fixture's diff to reviewer calls and records results.

Threading: synchronous, single thread. This module (the main thread) owns the CostTracker and
the results file; providers are stateless and nothing else reaches either.

Per fixture there are three call kinds: A (model A), B (model B) and B_after_A (model B shown
A's findings). The reviewer configs "A", "B" and "A then B" are derived from these at scoring
time; A-then-B reuses the A call, so A is never billed twice.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from swiss_cheese_bench.config import BenchConfig, ModelSpec
from swiss_cheese_bench.findings import Finding, parse_findings
from swiss_cheese_bench.fixtures import Category, Fixture
from swiss_cheese_bench.prompt import Prompt, build_prompt
from swiss_cheese_bench.providers import Provider, ProviderError

REQUEST_OVERHEAD_BYTES = 1024
KINDS = ("A", "B", "B_after_A")
MODEL_FOR_KIND = {"A": "A", "B": "B", "B_after_A": "B"}


def usage_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * spec.usd_per_mtok_in + output_tokens * spec.usd_per_mtok_out) / 1e6


@dataclass
class CostTracker:
    """Reserve-before-send cost cap. `committed` = actual spend + outstanding reservations.

    A reservation is the pessimistic worst case (>= 1 token per request byte in, full
    max_tokens out). It is replaced by actual usage on success and stays charged on error,
    since a failed or timed-out call may still have been billed.
    """

    cap_usd: float
    committed: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.cap_usd) or self.cap_usd < 0:
            raise ValueError("cap must be finite and >= 0")

    def worst_case(self, spec: ModelSpec, prompt: Prompt, max_out: int) -> float:
        request_bytes = (
            len(prompt.system.encode()) + len(prompt.user.encode()) + REQUEST_OVERHEAD_BYTES
        )
        return usage_cost(spec, request_bytes, max_out)

    def reserve(self, amount: float) -> bool:
        if self.committed + amount > self.cap_usd:
            return False
        self.committed += amount
        return True

    def settle(self, reserved: float, actual: float) -> None:
        self.committed += actual - reserved


@dataclass
class RunSummary:
    dry_run: bool
    cap_usd: float
    status_counts: dict[str, int] = field(default_factory=dict)
    spent_usd: float = 0.0
    projected_usd: float = 0.0
    committed_usd: float = 0.0


def _record(fixture: Fixture, case_no: int, kind: str, status: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "case_no": case_no,
        "fixture_id": fixture.id,
        "kind": kind,
        "model_key": MODEL_FOR_KIND[kind],
        "status": status,
        "raw_text": None,
        "findings": [],
        "parse_ok": False,
        "invalid": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "projected_cost_usd": 0.0,
        "error": None,
    }
    base.update(extra)
    return base


def _one_call(
    fixture: Fixture,
    case_no: int,
    kind: str,
    prior: list[Finding] | None,
    config: BenchConfig,
    provider: Provider,
    tracker: CostTracker,
    dry_run: bool,
) -> dict[str, Any]:
    spec = config.models[MODEL_FOR_KIND[kind]]
    prompt = build_prompt(fixture, case_no, prior)
    reserved = tracker.worst_case(spec, prompt, config.max_output_tokens)
    if not tracker.reserve(reserved):
        return _record(fixture, case_no, kind, "skipped_cost_cap")
    try:
        done = provider.complete(
            spec.model_id, prompt.system, prompt.user, config.max_output_tokens, config.timeout_s
        )
    except ProviderError as exc:
        # reservation stays charged: the provider may have billed this call
        err = _record(fixture, case_no, kind, "error", error=str(exc))
        err["projected_cost_usd" if dry_run else "cost_usd"] = reserved
        return err
    actual = usage_cost(spec, done.input_tokens, done.output_tokens)
    if not math.isfinite(actual):
        err = _record(fixture, case_no, kind, "error", error="invalid usage in response")
        err["projected_cost_usd" if dry_run else "cost_usd"] = reserved
        return err
    if not dry_run:
        # Dry runs keep the worst-case reservation committed, so cap decisions preview what a
        # live run would do; simulated usage only feeds projected_cost_usd.
        tracker.settle(reserved, actual)
    parsed = parse_findings(done.text)
    return _record(
        fixture,
        case_no,
        kind,
        "dry_run" if dry_run else "ok",
        raw_text=done.text,
        findings=[f.to_json() for f in parsed.findings],
        parse_ok=parsed.parse_ok,
        invalid=parsed.invalid,
        input_tokens=done.input_tokens,
        output_tokens=done.output_tokens,
        cost_usd=0.0 if dry_run else actual,
        projected_cost_usd=actual if dry_run else 0.0,
    )


def _findings_from(record: dict[str, Any]) -> list[Finding]:
    return [
        Finding(Category(f["category"]), f["file"], f["line"], f["message"])
        for f in record["findings"]
    ]


def run_bench(
    fixtures: list[Fixture],
    config: BenchConfig,
    providers: Mapping[str, Provider],
    out_dir: Path,
    dry_run: bool,
) -> RunSummary:
    out_dir.mkdir(parents=True, exist_ok=True)
    tracker = CostTracker(config.cap_usd)
    summary = RunSummary(dry_run=dry_run, cap_usd=config.cap_usd)
    counts: Counter[str] = Counter()
    meta = {
        "dry_run": dry_run,
        "cap_usd": config.cap_usd,
        "max_output_tokens": config.max_output_tokens,
        "models": {
            k: {
                "provider": m.provider,
                "model_id": m.model_id,
                "usd_per_mtok_in": m.usd_per_mtok_in,
                "usd_per_mtok_out": m.usd_per_mtok_out,
            }
            for k, m in config.models.items()
        },
    }
    (out_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        for case_no, fixture in enumerate(fixtures, start=1):
            records: dict[str, dict[str, Any]] = {}
            for kind in KINDS:
                prior: list[Finding] | None = None
                if kind == "B_after_A":
                    dep = records["A"]
                    if dep["status"] not in ("ok", "dry_run"):
                        rec = _record(fixture, case_no, kind, "skipped_dependency")
                        records[kind] = rec
                        out.write(json.dumps(rec) + "\n")
                        counts[rec["status"]] += 1
                        continue
                    prior = _findings_from(dep)
                provider = providers[MODEL_FOR_KIND[kind]]
                rec = _one_call(fixture, case_no, kind, prior, config, provider, tracker, dry_run)
                records[kind] = rec
                out.write(json.dumps(rec) + "\n")
                out.flush()
                counts[rec["status"]] += 1
                summary.spent_usd += rec["cost_usd"]
                summary.projected_usd += rec["projected_cost_usd"]
    summary.status_counts = dict(counts)
    summary.committed_usd = tracker.committed
    meta["summary"] = {
        "status_counts": summary.status_counts,
        "spent_usd": summary.spent_usd,
        "projected_usd": summary.projected_usd,
        "committed_usd": summary.committed_usd,
    }
    (out_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return summary
