# Step 4: Markdown report, SVG chart, `report` CLI

Concurrency: none; pure string rendering over the `Scoring` from step 3, plus two file writes in
the CLI (main thread). No shared state.

## Modules
- report.py
  - `render_chart(scoring) -> str`: standalone SVG (stdlib string building, all text passed through
    `xml.sax.saxutils.escape`). Grouped bars: recall per defect category for A, B, A_then_B
    (colours #0072B2, #E69F00, #009E73; checked with the dataviz skill's validate_palette.js:
    passes, with a contrast WARN for the orange that is relieved by printed value labels and the
    Markdown tables carrying the same numbers). Value labels on bars, legend, axis 0-100%, `<title>`
    and `<desc>` for accessibility. Undefined recall (0 truth) is not drawn.
  - `render_report(scoring, chart_ref) -> str`: Markdown with sections: title + SIMULATED banner
    when dry-run; run info (models, cap, spend); coverage (cohort, excluded + reason); summary
    per config (catches, recall + Wilson 95% interval, precision, false positives, cost incurred,
    cost per true catch, unparsable/invalid counts); pairing lift (pair vs best single, marginal
    cost per extra catch, with an explicit small-sample caution and no significance claims);
    per-category precision/recall; overlap & blind-spot matrix (both / A only / B only / neither,
    A_then_B caught per bucket); blind-spot categories; chart; method notes (matching rules,
    cohort, cost definition). Undefined values print `n/a`. Model ids and other free text are
    escaped for Markdown table cells.
- cli.py: `report --run DIR [--fixtures DIR] [--out report.md]` -> writes the Markdown and
  `chart.svg` next to it (relative link); exit 2 with a message on ScoringError/FixtureError.

## Tests (tests/test_report.py)
- report for a synthetic perfect run and for a mixed run: exact numbers appear (catches, recall,
  cost per catch, matrix counts, blind-spot category), `n/a` for undefined, dry-run banner present
  only for dry runs and absent for live;
- chart is well-formed XML (ElementTree), has all 8 categories and 3 legend entries; hostile model
  id (`<script>`, `|`, newline) is escaped in both outputs;
- CLI end to end: `run --dry-run` then `report` writes report.md + chart.svg, link resolves,
  exit 0; bad run dir => exit 2.

## Out of scope
Statistical tests, HTML output, multi-run comparison.

## Done criteria
`bash scripts/check.sh`, then cross-review of the diff since step 2; I assess each finding, apply the ones I agree with (unattended run, see DECISIONS.md D-01), rerun check.sh, then commit.

## Changes after plan review
- Dry-run labels: costs read "projected" and actual spend $0.00 when dry_run.
- Chart file named `<report stem>.chart.svg`; both outputs are rendered first, written to temp
  files in the target dir and renamed into place; OSError => exit 2. Tests: two reports in one dir,
  write failure (read-only/nonexistent parent).
- Chart tests assert series mapping, bar heights for partial recall (e.g. 1/3), 0% and 100%, and
  that undefined-recall categories have no bars.
- Report reads run metadata through tolerant getters (non-dict models/summary => "?" / 0) and has
  tests for malformed metadata; no KeyError/TypeError can escape.
