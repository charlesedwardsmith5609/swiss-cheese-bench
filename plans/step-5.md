# Step 5: hard fixture tier (authored through Cursor), tier-aware run/scoring/report

Concurrency: none (synchronous, single thread, bounded subprocess calls to the `agent` CLI). No
new shared state; the authoring driver owns its output files and nothing else reads them while it
runs.

## Decisions (proposed, awaiting approval)
1. ADD a hard tier; keep the 24 easy fixtures unchanged so results stay comparable with
   runs/live-2.
2. Hard tier = 24 defective + 8 clean = 32 fixtures, exact grid below.
3. `run --tier` defaults to `easy` (current behaviour and cost); `hard` and `all` are explicit.
4. Fixtures are authored by non-Claude models through the Cursor CLI (below), then audited.
5. The paid hard-tier pilot happens only after you OK it.

## Exact hard inventory (ids `h_<lang>_<category>_<n>`, n counted per language+category)
Defective (24; python 10, go 10, terraform 4):
- unrelated_deletion: py, py, go
- dropped_requirement: py, go, go
- test_bypasses_route: py, go, go
- validation_disabled: py, py, go
- hardcoded_expected: py, go, go
- swallowed_error: py, py, go
- secret_logged: py, go, terraform
- overbroad_iam: terraform x3
Clean controls (8, ids `h_clean_<lang>_<n>`): python 3, go 3, terraform 2, each built around a
decoy (below). The grid is asserted exactly in tests (generalised per tier; easy unchanged).

## Data
- label.json gains `"tier": "easy" | "hard"` (absent => easy, so existing fixtures stay valid);
  meta.json unchanged. Fixture ids still must never reach prompts (already tested).
- fixtures/INVENTORY.md gains columns: tier, author model, why hard, audit verdict.

## Hard-fixture design (each defective fixture has exactly ONE defect)
- Shape: 3-6 changed files and 100-250 changed lines, where "changed lines" = added + removed hunk
  lines only (headers and context excluded). Bounds enforced in code and tests (upper and lower).
  Legit related changes plus noise (rename, reformat, import reorder, docstrings).
- unrelated_deletion: one guard/index/retry/cleanup line removed inside a refactor hunk.
- dropped_requirement: task lists 4-5 requirements; one is missing, the others convincingly
  implemented and tested.
- test_bypasses_route: most tests use the client; the authz/validation test calls the handler
  directly or mocks the auth dependency.
- validation_disabled: `extra="allow"` / `strict=False` style schema loosening, or a validator
  made optional via a default; not an outright deletion. (`verify=False` is TLS, not schema
  validation, so it is excluded.)
- hardcoded_expected: literals keyed on a test id / `PYTEST_CURRENT_TEST`, a lookup table of the
  test's inputs, or a cache seeded with the expected values.
- swallowed_error: `except Exception` that logs at debug and returns a plausible default; Go
  `if err != nil { return nil }` or an ignored error from a deferred/goroutine call.
- secret_logged: whole-struct/headers/env dumps (`%+v`, `repr(headers)`, `dict(os.environ)`), not a
  literal `password=`. All secret values in fixtures are obvious fakes.
- overbroad_iam: `iam:PassRole` on `*`, wildcard via a variable default, a Condition removed,
  trust policy widened inside a larger refactor.
- Clean-control decoys: correct code that looks like a trigger (a justified broad `except` that
  re-raises or records a metric, a wildcard inside a Deny, expected literals that are legitimately
  test data, a validator tightened elsewhere while a loose one is correctly scoped).

## Authoring: Cursor CLI, no Claude models
- Calls: `agent -p --mode=ask --model M "<prompt>"` (read-only ask mode, the same call the review
  scripts use; Cursor never writes to the repo).
- Authors: `grok-4.7-xhigh` (xAI, a third family) for unrelated_deletion, dropped_requirement,
  test_bypasses_route, validation_disabled and 4 of the clean controls; `gpt-5.6-sol-xhigh`
  (OpenAI) for hardcoded_expected, swallowed_error, secret_logged, overbroad_iam and the other 4
  clean controls. Splitting authorship means neither reviewer family writes all the fixtures.
  Excluded: claude-fable-5-thinking-xhigh (same family as model A, flagged NO ZDR) and all Claude
  models. If a chosen model id is unavailable the driver fails loudly; I ask, never substitute.
- One request per fixture (32 calls). Each prompt has the exact target cell (category, language,
  id, theme), the JSON output schema, the design rules above and one easy fixture as a format
  example. Reply: one JSON object `{"task","base":{path:text},"after":{path:text},
  "label":{"category","file","description","evidence"},"why_hard"}`.
- New module swiss_cheese_bench/authoring.py (stdlib):
  - `parse_authored(text, cell) -> Authored`: extracts the JSON (fences/prose tolerated) and
    validates: relative POSIX paths only (no absolute, `..`, drive letters, hidden or `.git`
    components), <= 8 files and <= 64 KiB per file, UTF-8, LF only, language-appropriate suffixes,
    field length limits, id/category/tier come from the requested cell (not from the model), the
    task text contains no category name, evidence lies in a changed line (existing validate()),
    diff within the 100-250 line and 3-6 file bounds.
  - `materialize(authored, root)`: writes into a fresh staging directory (under root, same
    filesystem), regenerates diff.patch via make_diff, validates with load_fixture, then renames
    to fixtures/<id>/ atomically. Refuses to replace an existing id; removes the staging
    directory on every failure; never follows symlinks.
  - Driver `python -m swiss_cheese_bench.authoring run --cell ID [--model M]`: calls `agent` with
    an argument list (no shell) and a timeout, saves the raw reply under .reviews/authoring/
    (gitignored; reply capture capped at 1 MiB, larger => rejected, stderr capped too), materializes only if validation passes, at most 2 retries per cell with the
    validation error fed back. Authored text is DATA: never executed or imported.
- Privacy/cost: Cursor usage is billed to your Cursor plan, and the prompts and generated code are
  sent to Cursor. Prompts contain only this project's fixture material.

## Semantic audit gate (before any paid pilot)
Structural tests cannot prove "exactly one defect". For every hard fixture I read all changed
files and the label, and record an audit line in INVENTORY.md: defect present at label.file /
evidence; no second defect of any of the 8 categories anywhere in the diff; for clean controls,
nothing from the 8 categories is actually wrong. A second independent check sends each fixture to
grok-4.7-xhigh (never an OpenAI or Claude model, so evaluator families stay out of the audit) for
all OpenAI-authored fixtures, asking "list every defect you see in this diff" and comparing with
the label; Grok-authored fixtures are audited by me and by you (no model audit). Any extra defect
=> fixture fixed or dropped. Because B's family authored half the set, the first pilot is labelled
in-sample. You
spot-check the audit table before the pilot.

## Runner / scoring / report changes
- fixtures.py: `Label.tier` (validated), `Fixture.tier`.
- runner/cli: `run --tier easy|hard|all` (default easy). run.json records `tier` and a manifest
  (sorted fixture ids run).
- Compatibility: legacy run.json without a manifest (e.g. runs/live-2) is treated as
  easy-tier-only. `score_run` and `report` take the fixture list from the manifest; a manifest id
  with no fixture in the fixtures dir, or rows for ids outside the manifest, is a ScoringError.
- Cost attribution: each slice sums only the calls for fixtures in that slice; `all` is the sum of
  both tiers.
- scoring.py: `score_run(run_dir, fixtures)` returns complete slices for `easy`, `hard`, and `all`
  (those present in the manifest), each with its own cohort, per-category precision/recall,
  overlap matrix, blind spots, coverage/exclusions, and cost per catch (the same fields as today).
- report.py / cli report: sections for each slice present (hard first), each with summary,
  per-category P/R, overlap matrix, blind spots and cost; the chart is per category for the hard
  slice when present, else easy; `report --tier` picks the headline slice.

## Tests
- Fixtures: per-tier exact grid; hard diffs: 3-6 files and 100-250 +/- lines; evidence in diff;
  committed diff == regenerated; diff applies to base and reproduces after; task text has no
  category names; absent tier => easy, unknown tier => FixtureError.
- Authoring (tests/test_authoring.py, no Cursor calls, no network): parse_authored accepts
  fenced/prose-wrapped JSON and rejects traversal / absolute / hidden paths, oversized or too many
  files, non-UTF-8, missing keys, evidence not in diff, category words in task, size bounds;
  cell-provided id/category/tier override model-supplied ones; materialize output passes
  load_fixtures(); a fake `agent` script (path injected via an option, in tmp_path) verifies
  the driver passes model and prompt as arguments, enforces the timeout, retries with the
  validation error, and writes nothing outside fixtures/<id>/ except the raw reply under .reviews/authoring/; oversized
  replies and failed materializations leave no partial fixture or staging directory.
- Scoring/report: slices hand-computed on synthetic runs; legacy-manifest compatibility; manifest
  mismatches raise; `run --tier` and `report` end to end with dry run; all existing tests pass.

## Calibration (costs real money; needs your OK)
After check.sh passes and the audit table is spot-checked: one live pilot on the hard tier with the
current bench.json (about $0.5-1.5, cap $2).
Acceptance (R5), BOTH required: (a) EVERY single model (A and B) has hard-tier recall between
40% and 90% inclusive, and (b) at least one defect is caught by exactly one of A and B. If either fails, the step is reported as NOT MET against R5, the failed
calibration is recorded in DECISIONS.md, and I ask you how to redesign; no second paid pilot
without your OK. Any later result on revised fixtures is labelled in-sample calibration (the same
models informed the revision), never independent validation.
Caveat in the report: fixtures were authored by Grok and OpenAI models (not Claude), which reduces
but does not remove author/reviewer family effects; B shares a family with half the authors, so
the report states each fixture's author model.

## Out of scope
Repeats per fixture, new categories, reviewer prompt tuning, runner error-accounting changes (still
an open suggestion).

## Done criteria
`bash scripts/check.sh` (four stages) after each change; plan-review before code; cross-review of
the code at the end.
