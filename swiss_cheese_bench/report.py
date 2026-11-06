"""Markdown report and SVG chart rendering. Threading: none; pure string building."""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

from swiss_cheese_bench.fixtures import DEFECT_CATEGORIES
from swiss_cheese_bench.scoring import BUCKETS, CONFIGS, OVERALL, ConfigScore, Scoring

SERIES = (("A", "#0072B2"), ("B", "#E69F00"), ("A_then_B", "#009E73"))
CONFIG_LABEL = {
    "A": "A",
    "B": "B",
    "A_then_B": "A then B",
    "A_union_B": "A ∪ B (independent)",
}

# chart geometry (pixels)
CH_W, CH_H = 920, 440
PLOT_L, PLOT_R, PLOT_T, PLOT_B = 60, 20, 70, 110
BAR_W, BAR_GAP = 16, 3


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def md_cell(text: object) -> str:
    out = str(text).replace("\\", "\\\\").replace("|", "\\|").replace("`", "'")
    out = out.replace("<", "&lt;").replace(">", "&gt;")
    return " ".join(out.split())


def _model_field(models: object, key: str, name: str) -> str:
    if isinstance(models, dict):
        entry = models.get(key)
        if isinstance(entry, dict) and name in entry:
            return str(entry[name])
    return "?"


def _summary_num(summary: object, name: str) -> float:
    if isinstance(summary, dict):
        value = summary.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    return 0.0


def chart_geometry(recall: float, plot_h: float) -> float:
    """Bar height in pixels for a recall in [0, 1]."""
    return max(0.0, min(1.0, recall)) * plot_h


def render_chart(scoring: Scoring) -> str:
    cats = [str(c) for c in DEFECT_CATEGORIES]
    plot_w = CH_W - PLOT_L - PLOT_R
    plot_h = CH_H - PLOT_T - PLOT_B
    group_w = plot_w / len(cats)
    base_y = PLOT_T + plot_h
    suffix = " (SIMULATED dry run)" if scoring.dry_run else ""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CH_W}" height="{CH_H}" '
        f'viewBox="0 0 {CH_W} {CH_H}" role="img" aria-labelledby="t d" '
        'font-family="sans-serif" font-size="12">',
        f'<title id="t">Recall by defect category{xml_escape(suffix)}</title>',
        '<desc id="d">Grouped bars: share of seeded defects caught per category by reviewer A, '
        "reviewer B, and A then B.</desc>",
        f'<rect width="{CH_W}" height="{CH_H}" fill="#fcfcfb"/>',
        f'<text x="{PLOT_L}" y="24" font-size="15" font-weight="bold" fill="#222">'
        f"Recall by defect category{xml_escape(suffix)}</text>",
    ]
    for i, (key, colour) in enumerate(SERIES):  # legend
        lgx = PLOT_L + i * 130
        parts.append(f'<rect x="{lgx}" y="38" width="12" height="12" rx="2" fill="{colour}"/>')
        parts.append(
            f'<text x="{lgx + 18}" y="48" fill="#444">{xml_escape(CONFIG_LABEL[key])}</text>'
        )
    for tick in (0, 0.25, 0.5, 0.75, 1.0):  # recessive grid
        y = base_y - tick * plot_h
        parts.append(
            f'<line x1="{PLOT_L}" y1="{y:.1f}" x2="{CH_W - PLOT_R}" y2="{y:.1f}" '
            'stroke="#e3e3e0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PLOT_L - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#666">'
            f"{int(tick * 100)}%</text>"
        )
    series_w = len(SERIES) * BAR_W + (len(SERIES) - 1) * BAR_GAP
    for gi, cat in enumerate(cats):
        gx = PLOT_L + gi * group_w + (group_w - series_w) / 2
        for si, (key, colour) in enumerate(SERIES):
            recall = scoring.configs[key].categories[cat].recall
            if recall is None:
                continue
            x = gx + si * (BAR_W + BAR_GAP)
            h = chart_geometry(recall, plot_h)
            y = base_y - h
            parts.append(
                f'<rect class="bar" data-series="{key}" data-category="{cat}" '
                f'data-recall="{recall:.4f}" x="{x:.1f}" y="{y:.1f}" width="{BAR_W}" '
                f'height="{h:.1f}" fill="{colour}"/>'
            )
            parts.append(
                f'<text x="{x + BAR_W / 2:.1f}" y="{y - 3:.1f}" text-anchor="middle" '
                f'font-size="10" fill="#333">{recall * 100:.0f}</text>'
            )
        lx = PLOT_L + gi * group_w + group_w / 2
        parts.append(
            f'<text x="{lx:.1f}" y="{base_y + 14}" text-anchor="end" fill="#444" '
            f'transform="rotate(-35 {lx:.1f} {base_y + 14})">{xml_escape(cat)}</text>'
        )
    parts.append(
        f'<line x1="{PLOT_L}" y1="{base_y}" x2="{CH_W - PLOT_R}" y2="{base_y}" '
        'stroke="#888" stroke-width="1"/>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _summary_rows(scoring: Scoring) -> list[str]:
    cost_word = "projected cost" if scoring.dry_run else "cost incurred"
    lines = [
        f"| config | catches | recall (95% CI) | precision | false pos. | {cost_word} "
        f"| {cost_word}/catch | unparsable | dropped items |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in CONFIGS:
        c: ConfigScore = scoring.configs[name]
        o = c.overall
        ci = (
            f"{pct(o.recall)} ({pct(c.recall_interval[0])}–{pct(c.recall_interval[1])})"
            if c.recall_interval
            else "n/a"
        )
        lines.append(
            f"| {CONFIG_LABEL[name]} | {o.tp}/{o.truth} | {ci} | {pct(o.precision)} "
            f"| {o.false_positives} | {usd(c.cost_incurred_usd)} | {usd(c.cost_per_true_catch)} "
            f"| {c.n_unparsable} | {c.n_invalid_items} |"
        )
    return lines


def _extras_section(scoring: Scoring, h: str) -> list[str]:
    if scoring.configs["A"].extras is None:
        return [
            h + " Extra findings (not the seeded defect)",
            "",
            "Not adjudicated for this run (run `adjudicate` to judge the extra findings).",
            "",
        ]
    out = [
        h + " Extra findings (not the seeded defect)",
        "",
        f"Each distinct extra finding was judged by `{md_cell(scoring.adjudicator)}` (one model; "
        "check the sample in adjudication_sample.md). Counts are distinct (fixture, category, "
        'file) extras per config; "adjusted precision" counts real extras as correct.',
        "",
        "| config | real | not real | unclear | precision | adjusted precision |",
        "|---|---|---|---|---|---|",
    ]
    for name in CONFIGS:
        cfg = scoring.configs[name]
        ex = cfg.extras
        assert ex is not None  # noqa: S101 - all configs are set together
        out.append(
            f"| {CONFIG_LABEL[name]} | {ex.real} | {ex.not_real} | {ex.unclear} "
            f"| {pct(cfg.overall.precision)} | {pct(cfg.adjusted_precision)} |"
        )
    ov = scoring.extras_overlap
    if ov is not None:
        out += [
            "",
            f"Over the {ov.fixtures} fixtures both A and B were scored on: real extras found only "
            f"by A: {ov.real_a_only}; only by B: {ov.real_b_only}; by both: {ov.real_both} "
            f"(all extras, real or not: A only {ov.all_a_only}, B only {ov.all_b_only}, "
            f"both {ov.all_both}).",
        ]
    return out + [""]


def _slice_body(scoring: Scoring, h: str) -> list[str]:
    out: list[str] = []
    out += ["", h + " Summary by reviewer config", ""] + _summary_rows(scoring) + [""]

    single_best = scoring.marginal[0].best_single if scoring.marginal else "A"
    out += [h + " Does pairing help?", ""]
    for m in scoring.marginal:
        gain = (
            f"{m.extra_catches:+d} catches vs the best single model ({single_best})"
            f" for {'a saving of ' if m.extra_cost_usd < 0 else ''}${abs(m.extra_cost_usd):.4f}"
        )
        per = f" (${m.cost_per_extra_catch:.4f} per extra catch)" if m.cost_per_extra_catch else ""
        out.append(f"- **{CONFIG_LABEL[m.config]}**: {gain}{per}")
    out += [
        "",
        f"With only {scoring.configs['A'].overall.truth} seeded defects, differences of one or two "
        "catches are within noise (see the Wilson intervals above). Treat this as a measurement "
        "of this fixture set, not a general claim.",
        "",
        h + " Precision and recall by category",
        "",
        "| category | " + " | ".join(f"{CONFIG_LABEL[c]} P / R" for c in CONFIGS) + " |",
        "|---|" + "---|" * len(CONFIGS),
    ]
    for cat in [str(c) for c in DEFECT_CATEGORIES] + [OVERALL]:
        cells = []
        for name in CONFIGS:
            s = scoring.configs[name].categories[cat]
            cells.append(f"{pct(s.precision)} / {pct(s.recall)} ({s.tp}/{s.truth})")
        out.append(f"| {cat} | " + " | ".join(cells) + " |")
    out += [
        "",
        h + " Overlap and blind-spot matrix (A vs B)",
        "",
        "Counts of seeded defects by who caught them. The last column shows how many of each "
        "bucket the sequential A-then-B review caught.",
        "",
        "| category | both | A only | B only | neither | A then B caught (both/A/B/neither) |",
        "|---|---|---|---|---|---|",
    ]
    for r in scoring.overlap:
        caught = "/".join(str(r.a_then_b_caught[b]) for b in BUCKETS)
        out.append(
            f"| {r.category} | {r.counts['both']} | {r.counts['A_only']} | {r.counts['B_only']} "
            f"| {r.counts['neither']} | {caught} |"
        )
    spots = scoring.blind_spots
    spots = scoring.blind_spots
    out += [
        "",
        "Blind spots (defects neither model caught): "
        + (", ".join(f"`{s}`" for s in spots) if spots else "none"),
        "",
    ]
    return out + _extras_section(scoring, h)


def _cohort_lines(scoring: Scoring) -> list[str]:
    lines = [
        f"- Cohort: {len(scoring.cohort)} fixtures scored by every config; "
        f"{len(scoring.excluded)} excluded"
    ]
    for fid, why in sorted(scoring.excluded.items()):
        lines.append(f"  - excluded `{md_cell(fid)}`: {md_cell(why)}")
    return lines


TIER_TITLE = {"hard": "Hard tier", "easy": "Easy tier", "all": "All fixtures combined"}


def render_report(
    scoring: Scoring | dict[str, Scoring], chart_ref: str, chart_tier: str | None = None
) -> str:
    """One Scoring renders as before; a dict of slices renders hard, easy, then all."""
    slices = {"": scoring} if isinstance(scoring, Scoring) else scoring
    first = next(iter(slices.values()))
    meta = first.meta
    out: list[str] = ["# swiss-cheese-bench report", ""]
    if first.dry_run:
        out += [
            "> **SIMULATED RESULTS (dry run).** No model was called and nothing was spent. The "
            "findings come from a deterministic fake reviewer, so every number below only "
            "demonstrates the pipeline; none of it says anything about real models. Costs are "
            "projections at the configured prices.",
            "",
        ]
    spent = _summary_num(meta.summary, "spent_usd")
    out += [
        "## Run",
        "",
        f"- Model A: `{md_cell(_model_field(meta.models, 'A', 'provider'))}` / "
        f"`{md_cell(_model_field(meta.models, 'A', 'model_id'))}`",
        f"- Model B: `{md_cell(_model_field(meta.models, 'B', 'provider'))}` / "
        f"`{md_cell(_model_field(meta.models, 'B', 'model_id'))}`",
        f"- Cost cap: ${meta.cap_usd:.2f}; actual spend: ${spent:.4f}",
    ]
    if isinstance(scoring, Scoring):
        out += _cohort_lines(scoring)
        out += _slice_body(scoring, "##")
    else:
        order = [t for t in ("hard", "easy", "all") if t in slices]
        for tier in order:
            out += ["", f"## {TIER_TITLE[tier]}", ""] + _cohort_lines(slices[tier])
            out += _slice_body(slices[tier], "###")
    chart_title = "Recall by defect category" + (
        "" if isinstance(scoring, Scoring) else f" ({TIER_TITLE[chart_tier or order[0]].lower()})"
    )
    out += [
        "## Chart",
        "",
        f"![{chart_title}]({chart_ref})",
        "",
        "## Method notes",
        "",
        "- A finding is a catch only if its category and file both match the ground truth; a "
        "finding with no file counts as a false positive. Findings are deduplicated per "
        "(category, file) per fixture.",
        "- All comparisons use the cohort of fixtures every config scored. API errors and "
        "cost-cap skips are unscored; unparsable model output counts as a miss.",
        "- Precision includes findings on clean control fixtures. `n/a` means the denominator "
        "was zero.",
        "- Cost per true catch divides ALL cost incurred on the slice's fixtures (including failed "
        "calls and fixtures outside the cohort) by cohort catches, so it can overstate cost. "
        "Each slice counts only its own fixtures' calls. A then B includes A's call cost plus "
        "B's follow-up call.",
        "- A ∪ B merges independent A and B findings; A then B shows B A's findings and uses "
        "B's final list.",
        "",
    ]
    return "\n".join(out)
