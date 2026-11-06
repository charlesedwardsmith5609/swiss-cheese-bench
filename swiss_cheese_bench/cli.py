"""Command line entry point. Threading: none (single thread)."""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from swiss_cheese_bench.config import ConfigError, load_config
from swiss_cheese_bench.fixtures import FixtureError, load_fixtures
from swiss_cheese_bench.providers import Provider, ProviderError, make_provider
from swiss_cheese_bench.runner import run_bench


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swiss_cheese_bench")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="send fixture diffs to the reviewer models")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    run.add_argument("--out", type=Path, default=Path("runs/latest"))
    run.add_argument("--cap-usd", type=float, default=None, help="override the config cap")
    run.add_argument("--dry-run", action="store_true", help="no network, nothing spent")
    args = parser.parse_args(argv)
    environ = os.environ if env is None else env
    try:
        config = load_config(args.config)
        if args.cap_usd is not None:
            config = dataclasses.replace(config, cap_usd=args.cap_usd)
        fixtures = load_fixtures(args.fixtures)
        providers: dict[str, Provider] = {
            key: make_provider(spec, environ, args.dry_run) for key, spec in config.models.items()
        }
        summary = run_bench(fixtures, config, providers, args.out, args.dry_run)
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
