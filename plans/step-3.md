# Step 3: scoring (precision/recall per category, overlap matrix, cost per true catch)

Concurrency: none. Pure, synchronous functions over `<run>/results.jsonl` + fixture labels. No
shared state; nothing is written (the report in step 4 renders the returned data).

## Module swiss_cheese_bench/scoring.py
- `load_results(run_dir, fixtures) -> (RunMeta, list[CallRow])`: parses run.json + results.jsonl.
  run.json must carry the finalized `summary` (an interrupted run has none => ScoringError), and
  results.jsonl must hold exactly one row for each of A, B, B_after_A for every supplied fixture,
  with no unknown fixture ids. Full row schema validation: field types, kind/status/category enums,
  finite non-negative costs and token counts, dry_run flag consistent with status (`dry_run` iff
  run.json dry_run), findings list well-formed. Any violation raises `ScoringError` (no silent
  skipping: a half-read run would bias every metric).
- Reviewer configs derived from calls (names: `A`, `B`, `A_then_B`, `A_union_B`):
  - A = call A; B = call B; A_then_B = findings of `B_after_A` (B is the final arbiter);
  - A_union_B = union of independently produced A and B findings (derived, no extra calls; it is
    the "do two independent reviewers beat one" view).
  - Cost: A, B = own call; A_then_B = A + B_after_A; A_union_B = A + B. Dry-run runs use
    `projected_cost_usd` (and the Scoring result carries `dry_run=True` so the report can label
    all numbers SIMULATED); live runs use `cost_usd`.
- Scored vs unscored (per fixture x config): scored iff every required call has status ok/dry_run.
  error / skipped_* => unscored: excluded from every denominator and reported as coverage
  (`n_scored/n_total`). A call whose output did not parse (`parse_ok` false) is scored as zero
  findings (a miss) and counted in `n_unparsable`: a model that cannot follow the schema has failed
  at review.
- Matching: a finding is correct for a fixture iff finding.category == label.category and its file
  (normalised: strip `a/`/`b/`/`./` prefixes) equals label.file. A finding naming no file is never
  a catch (it counts as a false positive in its category).
  Findings are deduplicated per fixture by (category, normalised file) before counting.
- Common cohort: all comparative numbers (per-category precision/recall, overlap matrix, lift,
  marginal cost) are computed on the cohort = fixtures for which EVERY config is scored, so configs
  are compared on identical cases. Coverage lists cohort size, excluded fixtures and why.
- Per config, per defect category k (and an overall micro row):
  truth_k = scored fixtures labelled k; predicted_k = distinct findings of category k on ALL scored
  fixtures (clean controls included, so false positives there cost precision);
  tp_k = truth fixtures of category k with a correct finding.
  precision_k = tp_k / predicted_k, recall_k = tp_k / truth_k; `None` when the denominator is 0
  (never reported as 0 or 1). Overall recall also gets a Wilson 95% interval (stdlib maths) because
  n is ~20 and differences are easily noise.
- Overlap / blind-spot matrix (A vs B), over truth fixtures scored for both: per category counts
  of `both`, `A_only`, `B_only`, `neither`, plus a total row; and for each bucket how many
  `A_then_B` caught out of how many were eligible (`a_then_b_caught`/`a_then_b_scored`), so it shows whether sequential review rescues B-only
  cases without losing A-only ones. `blind_spots`: categories whose `neither` > 0.
- Cost: `cost_incurred_usd` per config sums ALL its required calls on ALL fixtures regardless of
  status (failed calls keep their reservation charged, so money wasted on errors is not hidden);
  `true_catches` (= cohort tp overall); `cost_per_true_catch` = cost_incurred / true_catches
  (conservative: includes spend outside the cohort; None if 0 catches), and marginal cost of a pair over the best single
  model: (cost_pair - cost_best_single) / (tp_pair - tp_best_single) when tp gain > 0, else None.
- Malformed output: per config `n_unparsable` (output without a valid findings object) and
  `n_invalid_items` (sum of dropped malformed items over the calls that make up the config's
  findings: A: A; B: B; A_then_B: B_after_A; A_union_B: A + B).
- `score_run(run_dir, fixtures) -> Scoring` ties it together. No file writing, no network.

## Tests (tests/test_scoring.py), synthetic results.jsonl built over the real fixtures
- perfect reviewer: precision = recall = 1 for each category, clean controls produce no findings;
- wrong file, wrong category, duplicate finding, finding on a clean fixture, finding with no file,
  `b/` prefixed path: each asserted against hand-computed tp/predicted;
- failed/skipped calls are unscored, excluded from the cohort (coverage reported) but their cost
  stays in cost_incurred; a finding with no file is a false positive; unparsable
  output counts as a miss and in n_unparsable;
- overlap buckets with a hand-built A/B catch pattern incl. A_then_B rescue counts;
- cost: live uses cost_usd, dry-run uses projected_cost_usd; cost-per-catch and marginal cost
  hand-computed; zero catches => None;
- None (not 0) for undefined precision/recall; Wilson interval known values;
- malformed run dir (bad JSON line, unknown fixture id, duplicate row, missing file, truncated
  run without summary, missing rows, wrong types, negative/NaN cost, dry-run inconsistency)
  => ScoringError; invalid-item counts aggregated.

## Out of scope
Markdown/chart rendering and CLI `report` subcommand (step 4); statistical significance tests.

## Done criteria
`bash scripts/check.sh`; report ruff check, ruff format --check, mypy, pytest.
