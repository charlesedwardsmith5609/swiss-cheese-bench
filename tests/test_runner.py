from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from swiss_cheese_bench.cli import main
from swiss_cheese_bench.config import BenchConfig, ModelSpec
from swiss_cheese_bench.fixtures import Fixture, load_fixtures
from swiss_cheese_bench.providers import AnthropicProvider, DryRunProvider, OpenAIProvider, Provider
from swiss_cheese_bench.runner import CostTracker, run_bench
from tests.stub_server import StubServer, anthropic_reply, openai_reply

ROOT = Path(__file__).resolve().parent.parent / "fixtures"
KEY_A, KEY_B = "fake-aaaa-one", "fake-bbbb-two"
FINDING = '{"findings": [{"category": "swallowed_error", "file": "x", "message": "m"}]}'


@pytest.fixture(scope="module")
def few() -> list[Fixture]:
    return load_fixtures(ROOT)[:3]


@pytest.fixture
def stubs() -> Iterator[tuple[StubServer, StubServer]]:
    a = StubServer(lambda p, h, b: (200, anthropic_reply(FINDING, 1000, 100)))
    b = StubServer(lambda p, h, b: (200, openai_reply(FINDING, 1000, 100)))
    yield a, b
    a.close()
    b.close()


def _cfg(a_url: str | None, b_url: str | None, cap: float = 100.0) -> BenchConfig:
    return BenchConfig(
        models={
            "A": ModelSpec("A", "anthropic", "ma", 1.0, 2.0, "SCB_A", a_url),
            "B": ModelSpec("B", "openai", "mb", 3.0, 4.0, "SCB_B", b_url),
        },
        max_output_tokens=200,
        timeout_s=5.0,
        cap_usd=cap,
    )


def _rows(out: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]


def test_live_run_costs_and_call_structure(
    tmp_path: Path, few: list[Fixture], stubs: tuple[StubServer, StubServer]
) -> None:
    sa, sb = stubs
    cfg = _cfg(sa.base_url, sb.base_url)
    providers: dict[str, Provider] = {
        "A": AnthropicProvider(KEY_A, sa.base_url),
        "B": OpenAIProvider(KEY_B, sb.base_url),
    }
    summary = run_bench(few, cfg, providers, tmp_path, dry_run=False)
    rows = _rows(tmp_path)
    assert [r["kind"] for r in rows] == ["A", "B", "B_after_A"] * 3
    assert {r["status"] for r in rows} == {"ok"}
    a_cost = (1000 * 1.0 + 100 * 2.0) / 1e6
    b_cost = (1000 * 3.0 + 100 * 4.0) / 1e6
    assert rows[0]["cost_usd"] == pytest.approx(a_cost)
    assert rows[1]["cost_usd"] == pytest.approx(b_cost)
    assert summary.spent_usd == pytest.approx(3 * (a_cost + 2 * b_cost))
    assert summary.committed_usd == pytest.approx(summary.spent_usd)
    assert len(sa.snapshot()) == 3 and len(sb.snapshot()) == 6
    # B_after_A prompt contains A's findings; plain B prompt does not
    bodies = [json.loads(r["body"])["messages"][1]["content"] for r in sb.snapshot()]
    assert "Another reviewer" not in bodies[0] and "Another reviewer" in bodies[1]
    # secrets and fixture ids never reach the results or the prompts
    blob = (tmp_path / "results.jsonl").read_text() + (tmp_path / "run.json").read_text()
    assert KEY_A not in blob and KEY_B not in blob
    for r in sa.snapshot() + sb.snapshot():
        assert not any(f.id.encode() in r["body"] for f in few)


def test_dry_run_makes_no_requests_and_spends_nothing(
    tmp_path: Path, few: list[Fixture], stubs: tuple[StubServer, StubServer]
) -> None:
    sa, sb = stubs
    cfg = _cfg(sa.base_url, sb.base_url)
    providers: dict[str, Provider] = {"A": DryRunProvider(), "B": DryRunProvider()}
    summary = run_bench(few, cfg, providers, tmp_path, dry_run=True)
    assert sa.snapshot() == [] and sb.snapshot() == []
    rows = _rows(tmp_path)
    assert {r["status"] for r in rows} == {"dry_run"}
    assert all(r["cost_usd"] == 0 and r["projected_cost_usd"] > 0 for r in rows)
    assert summary.spent_usd == 0 and summary.projected_usd > 0
    assert json.loads((tmp_path / "run.json").read_text())["dry_run"] is True


def test_cost_cap_stops_spending(
    tmp_path: Path, few: list[Fixture], stubs: tuple[StubServer, StubServer]
) -> None:
    sa, sb = stubs
    cap = 0.012  # worst-case reservation per call is several mUSD; room for only a few calls
    cfg = _cfg(sa.base_url, sb.base_url, cap=cap)
    providers: dict[str, Provider] = {
        "A": AnthropicProvider(KEY_A, sa.base_url),
        "B": OpenAIProvider(KEY_B, sb.base_url),
    }
    summary = run_bench(few, cfg, providers, tmp_path, dry_run=False)
    rows = _rows(tmp_path)
    statuses = [r["status"] for r in rows]
    assert "ok" in statuses and "skipped_cost_cap" in statuses
    assert summary.committed_usd <= cap + 1e-12
    assert summary.spent_usd <= cap + 1e-12
    assert len(sa.snapshot()) + len(sb.snapshot()) == statuses.count("ok")


def test_zero_cap_makes_no_calls(
    tmp_path: Path, few: list[Fixture], stubs: tuple[StubServer, StubServer]
) -> None:
    sa, sb = stubs
    providers: dict[str, Provider] = {
        "A": AnthropicProvider(KEY_A, sa.base_url),
        "B": OpenAIProvider(KEY_B, sb.base_url),
    }
    run_bench(few, _cfg(sa.base_url, sb.base_url, cap=0.0), providers, tmp_path, dry_run=False)
    assert sa.snapshot() == [] and sb.snapshot() == []
    statuses = {r["status"] for r in _rows(tmp_path)}
    assert statuses == {"skipped_cost_cap", "skipped_dependency"}


def test_failed_call_keeps_reservation_and_skips_dependent(
    tmp_path: Path, few: list[Fixture]
) -> None:
    sa = StubServer(lambda p, h, b: (500, b"boom"))
    sb = StubServer(lambda p, h, b: (200, openai_reply(FINDING, 10, 10)))
    try:
        providers: dict[str, Provider] = {
            "A": AnthropicProvider(KEY_A, sa.base_url),
            "B": OpenAIProvider(KEY_B, sb.base_url),
        }
        summary = run_bench(few[:1], _cfg(sa.base_url, sb.base_url), providers, tmp_path, False)
        rows = _rows(tmp_path)
        assert [r["status"] for r in rows] == ["error", "ok", "skipped_dependency"]
        assert rows[0]["cost_usd"] > 0  # reservation stays charged
        assert summary.committed_usd >= rows[0]["cost_usd"]
        assert len(sb.snapshot()) == 1
    finally:
        sa.close()
        sb.close()


def test_unparseable_output_is_recorded_not_fatal(tmp_path: Path, few: list[Fixture]) -> None:
    sa = StubServer(lambda p, h, b: (200, anthropic_reply("I refuse", 5, 5)))
    sb = StubServer(lambda p, h, b: (200, openai_reply("{}", 5, 5)))
    try:
        providers: dict[str, Provider] = {
            "A": AnthropicProvider(KEY_A, sa.base_url),
            "B": OpenAIProvider(KEY_B, sb.base_url),
        }
        run_bench(few[:1], _cfg(sa.base_url, sb.base_url), providers, tmp_path, False)
        rows = _rows(tmp_path)
        assert [r["parse_ok"] for r in rows] == [False, False, False]
        assert [r["status"] for r in rows] == ["ok", "ok", "ok"]
    finally:
        sa.close()
        sb.close()


def test_cost_tracker_rules() -> None:
    t = CostTracker(1.0)
    assert t.reserve(0.6) and not t.reserve(0.5)
    t.settle(0.6, 0.1)
    assert t.committed == pytest.approx(0.1) and t.reserve(0.9)
    with pytest.raises(ValueError):
        CostTracker(float("nan"))
    with pytest.raises(ValueError):
        CostTracker(-1)


def _write_cfg(path: Path, a_url: str | None = None, b_url: str | None = None) -> Path:
    spec = lambda k, p, env, url: {  # noqa: E731
        "provider": p,
        "model_id": k,
        "usd_per_mtok_in": 1,
        "usd_per_mtok_out": 1,
        "api_key_env": env,
        **({"base_url": url} if url else {}),
    }
    path.write_text(
        json.dumps(
            {
                "models": {
                    "A": spec("ma", "anthropic", "SCB_A", a_url),
                    "B": spec("mb", "openai", "SCB_B", b_url),
                },
                "max_output_tokens": 100,
                "timeout_s": 5,
                "cap_usd": 50,
            }
        )
    )
    return path


def test_cli_dry_run_needs_no_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_cfg(tmp_path / "c.json")
    code = main(["run", "--config", str(cfg), "--out", str(tmp_path / "o"), "--dry-run"], env={})
    assert code == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "spent $0.0000" in out
    assert len(_rows(tmp_path / "o")) == 72  # 24 fixtures x 3 calls


def test_cli_missing_key_exits_2_before_any_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _write_cfg(tmp_path / "c.json")
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")], env={}) == 2
    assert "SCB_A" in capsys.readouterr().err
    assert not (tmp_path / "o" / "results.jsonl").exists()


def test_cli_invalid_config_and_cap_override(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert main(["run", "--config", str(bad), "--dry-run"], env={}) == 2
    cfg = _write_cfg(tmp_path / "c.json")
    assert main(["run", "--config", str(cfg), "--dry-run", "--cap-usd", "-1"], env={}) == 2


def test_cli_live_run_against_stubs(tmp_path: Path, stubs: tuple[StubServer, StubServer]) -> None:
    sa, sb = stubs
    cfg = _write_cfg(tmp_path / "c.json", sa.base_url, sb.base_url)
    env = {"SCB_A": KEY_A, "SCB_B": KEY_B}
    assert (
        main(
            ["run", "--config", str(cfg), "--out", str(tmp_path / "o"), "--cap-usd", "50"], env=env
        )
        == 0
    )
    assert len(sa.snapshot()) == 24 and len(sb.snapshot()) == 48


def test_dry_run_cap_uses_worst_case_like_a_live_run(tmp_path: Path, few: list[Fixture]) -> None:
    providers: dict[str, Provider] = {"A": DryRunProvider(), "B": DryRunProvider()}
    cfg = _cfg(None, None, cap=0.012)
    summary = run_bench(few, cfg, providers, tmp_path, dry_run=True)
    statuses = [r["status"] for r in _rows(tmp_path)]
    assert "skipped_cost_cap" in statuses and "dry_run" in statuses
    assert summary.committed_usd <= 0.012 + 1e-12
    assert summary.spent_usd == 0
