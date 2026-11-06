from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from swiss_cheese_bench.cli import main
from swiss_cheese_bench.fixtures import Category, Fixture, load_fixtures
from swiss_cheese_bench.report import (
    CH_H,
    PLOT_B,
    PLOT_T,
    chart_geometry,
    md_cell,
    pct,
    render_chart,
    render_report,
)
from swiss_cheese_bench.scoring import score_run
from tests.test_scoring import DEFECTIVE, FIXTURES, perfect, truth, write_run

PLOT_H = CH_H - PLOT_T - PLOT_B
ROOT = Path(__file__).resolve().parent.parent / "fixtures"
EXAMPLE = Path(__file__).resolve().parent.parent / "bench.example.json"


def mixed(f: Fixture, kind: str) -> dict[str, Any]:
    """A misses the first defective fixture; B misses the second; B_after_A rescues it."""
    if kind == "A" and f is DEFECTIVE[0]:
        return {"findings": []}
    if kind == "B" and f is DEFECTIVE[1]:
        return {"findings": []}
    if f.label.category is Category.NONE:
        return {}
    return {"findings": [truth(f)]}


def bars(svg: str) -> dict[tuple[str, str], tuple[float, float]]:
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    out = {}
    for el in root.iter(f"{ns}rect"):
        if el.get("class") == "bar":
            out[(el.get("data-series", ""), el.get("data-category", ""))] = (
                float(el.get("data-recall", "nan")),
                float(el.get("height", "nan")),
            )
    return out


def test_report_numbers_and_sections(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, mixed), FIXTURES)
    md = render_report(s, "c.svg")
    assert "SIMULATED" not in md
    assert "| A | 19/20 | 95% (" in md
    assert "| A ∪ B (independent) | 20/20 |" in md
    assert "Blind spots (defects neither model caught): none" in md
    assert "![Recall by defect category](c.svg)" in md
    assert "cost incurred" in md and "$0.2400" in md  # A: 24 calls * 0.01
    assert "A ∪ B (independent)**: +1 catches vs the best single model (A)" in md
    total = re.search(r"\| overall \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| ([\d/]+) \|", md)
    assert total and total.group(1) == "18"  # both
    assert (total.group(2), total.group(3), total.group(4)) == ("1", "1", "0")


def test_dry_run_banner_and_projected_labels(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, perfect, dry_run=True), FIXTURES)
    md = render_report(s, "c.svg")
    assert "SIMULATED RESULTS" in md and "projected cost" in md and "actual spend: $0.0000" in md
    assert "SIMULATED" in render_chart(s)


def test_undefined_values_print_na(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, lambda f, k: {}), FIXTURES)
    md = render_report(s, "c.svg")
    assert "n/a" in md and pct(None) == "n/a"
    assert len(bars(render_chart(s))) == 24  # recall is defined (0%), so bars exist at 0 height
    assert all(h == 0 for _, h in bars(render_chart(s)).values())


def test_chart_geometry_and_series_mapping(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, mixed), FIXTURES)
    b = bars(render_chart(s))
    assert len(b) == 24
    a_cat = str(DEFECTIVE[0].label.category)
    b_cat = str(DEFECTIVE[1].label.category)
    assert b[("A", a_cat)][0] == pytest.approx(s.configs["A"].categories[a_cat].recall, abs=1e-4)
    assert b[("B", b_cat)][0] == pytest.approx(s.configs["B"].categories[b_cat].recall, abs=1e-4)
    for (_series, _cat), (recall, height) in b.items():
        assert height == pytest.approx(recall * PLOT_H, abs=0.06)
    assert any(r == 1.0 and h == pytest.approx(PLOT_H, abs=0.06) for r, h in b.values())
    partial = [r for r, _ in b.values() if 0 < r < 1]
    assert partial  # a category with two fixtures and one miss => 50%
    assert chart_geometry(2.0, 100) == 100 and chart_geometry(-1, 100) == 0


def test_chart_skips_bars_when_recall_undefined(tmp_path: Path) -> None:
    s = score_run(write_run(tmp_path, perfect), FIXTURES)
    from dataclasses import replace

    cat = str(DEFECTIVE[0].label.category)
    cfg = s.configs["A"]
    broken = replace(cfg.categories[cat], truth=0, tp=0)
    s.configs["A"] = replace(cfg, categories={**cfg.categories, cat: broken})
    b = bars(render_chart(s))
    assert ("A", cat) not in b and ("B", cat) in b


def test_hostile_text_is_escaped(tmp_path: Path) -> None:
    run = write_run(tmp_path, perfect)
    import json

    meta = json.loads((run / "run.json").read_text())
    meta["models"] = {"A": {"provider": "x|y", "model_id": "<script>alert(1)</script>\n| z"}}
    (run / "run.json").write_text(json.dumps(meta))
    s = score_run(run, FIXTURES)
    md = render_report(s, "c.svg")
    assert "<script>" not in md and "&lt;script&gt;" in md
    assert "x\\|y" in md
    ET.fromstring(render_chart(s))  # still well-formed
    assert md_cell("a|b`c") == "a\\|b'c"


def test_malformed_metadata_does_not_crash(tmp_path: Path) -> None:
    import json

    run = write_run(tmp_path, perfect)
    meta = json.loads((run / "run.json").read_text())
    meta["models"] = {"A": "not-a-dict", "B": {"provider": 5}}
    meta["summary"] = {"spent_usd": "lots"}
    (run / "run.json").write_text(json.dumps(meta))
    md = render_report(score_run(run, FIXTURES), "c.svg")
    assert "`?`" in md and "actual spend: $0.0000" in md


def test_cli_run_then_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    assert main(["run", "--config", str(EXAMPLE), "--out", str(run), "--dry-run"], env={}) == 0
    out = tmp_path / "out" / "a.md"
    out.parent.mkdir()
    assert main(["report", "--run", str(run), "--out", str(out)]) == 0
    out2 = tmp_path / "out" / "b.md"
    assert main(["report", "--run", str(run), "--out", str(out2)]) == 0
    for name in ("a", "b"):
        md = (out.parent / f"{name}.md").read_text()
        assert f"({name}.chart.svg)" in md and "SIMULATED" in md
        ET.fromstring((out.parent / f"{name}.chart.svg").read_text())
    assert not list(out.parent.glob(".scb-*"))
    assert load_fixtures(ROOT)  # fixtures untouched


def test_cli_report_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["report", "--run", str(tmp_path / "nope"), "--out", str(tmp_path / "r.md")]) == 2
    run = tmp_path / "run"
    assert main(["run", "--config", str(EXAMPLE), "--out", str(run), "--dry-run"], env={}) == 0
    # unwritable target (parent directory does not exist): exit 2, nothing left behind
    missing = tmp_path / "no_such_dir" / "r.md"
    assert main(["report", "--run", str(run), "--out", str(missing)]) == 2
    assert "error" in capsys.readouterr().err
    assert not (tmp_path / "no_such_dir").exists()
