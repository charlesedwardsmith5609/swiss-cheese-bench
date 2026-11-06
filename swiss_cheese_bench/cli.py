"""Command line entry point. Threading: none (single thread)."""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from swiss_cheese_bench.adjudicate import (
    DEFAULT_MODEL as DEFAULT_ADJUDICATOR,
)
from swiss_cheese_bench.adjudicate import AdjudicationError, adjudicate_run
from swiss_cheese_bench.config import ConfigError, load_config
from swiss_cheese_bench.fixtures import FixtureError, load_fixtures
from swiss_cheese_bench.providers import Provider, ProviderError, make_provider
from swiss_cheese_bench.report import render_chart, render_report
from swiss_cheese_bench.runner import run_bench
from swiss_cheese_bench.scoring import ScoringError, score_slices


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swiss_cheese_bench")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="send fixture diffs to the reviewer models")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    run.add_argument("--out", type=Path, default=Path("runs/latest"))
    run.add_argument("--cap-usd", type=float, default=None, help="override the config cap")
    run.add_argument(
        "--tier", choices=["easy", "hard", "all"], default="easy", help="which fixtures to run"
    )
    run.add_argument("--dry-run", action="store_true", help="no network, nothing spent")
    rep = sub.add_parser("report", help="score a finished run and write a Markdown report")
    rep.add_argument("--run", type=Path, required=True, help="run directory")
    rep.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    rep.add_argument("--out", type=Path, default=Path("report.md"))
    rep.add_argument(
        "--tier",
        choices=["easy", "hard", "all"],
        default=None,
        help="slice used for the chart (default: hard if the run has it, else easy)",
    )
    adj = sub.add_parser("adjudicate", help="judge a run's non-seeded findings via Cursor")
    adj.add_argument("--run", type=Path, required=True)
    adj.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    adj.add_argument("--model", default=DEFAULT_ADJUDICATOR)
    adj.add_argument("--jobs", type=int, default=4)
    adj.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "adjudicate":
        try:
            path = adjudicate_run(args.run, args.fixtures, args.model, args.jobs, args.force)
        except AdjudicationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {path}")
        return 0
    if args.command == "report":
        return _report(args.run, args.fixtures, args.out, args.tier)
    environ = os.environ if env is None else env
    try:
        config = load_config(args.config)
        if args.cap_usd is not None:
            config = dataclasses.replace(config, cap_usd=args.cap_usd)
        fixtures = load_fixtures(args.fixtures)
        if args.tier != "all":
            fixtures = [f for f in fixtures if f.tier == args.tier]
        if not fixtures:
            raise FixtureError(f"no fixtures in tier {args.tier!r}")
        providers: dict[str, Provider] = {
            key: make_provider(spec, environ, args.dry_run) for key, spec in config.models.items()
        }
        summary = run_bench(fixtures, config, providers, args.out, args.dry_run, args.tier)
    except (ConfigError, FixtureError, ProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    mode = "DRY RUN" if summary.dry_run else "LIVE"
    print(f"{mode}: calls {summary.status_counts}")
    print(
        f"spent ${summary.spent_usd:.4f}, projected ${summary.projected_usd:.4f}, "
        f"committed (incl. reservations) ${summary.committed_usd:.4f} of cap ${summary.cap_usd:.2f}"
    )
    print(f"results: {args.out}/results.jsonl")
    return 0


def _report(run_dir: Path, fixtures_dir: Path, out: Path, tier: str | None) -> int:
    """Render both files first, then replace them in place; any failure leaves no half report."""
    chart_path = out.with_name(out.stem + ".chart.svg")
    try:
        slices = score_slices(run_dir, load_fixtures(fixtures_dir))
        chart_tier = tier or next(t for t in ("hard", "easy", "all") if t in slices)
        if chart_tier not in slices:
            raise ScoringError(f"the run has no {chart_tier!r} slice (has {sorted(slices)})")
        chart = render_chart(slices[chart_tier])
        markdown = render_report(slices, chart_path.name, chart_tier)
        staged: list[tuple[Path, Path]] = []
        try:
            for target, text in ((chart_path, chart), (out, markdown)):
                fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".scb-", suffix=".tmp")
                tmp = Path(tmp_name)
                staged.append((tmp, target))
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
            for tmp, target in staged:
                tmp.replace(target)
        finally:
            for tmp, _ in staged:
                tmp.unlink(missing_ok=True)
    except (ScoringError, FixtureError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {out} and {chart_path}")
    return 0
