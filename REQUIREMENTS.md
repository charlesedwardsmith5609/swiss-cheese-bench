# Requirements: swiss-cheese-bench

Goal: measure whether pairing two different models as code reviewers catches more
agent-introduced defects than either alone.

Status: written by the agent under the user's "run unattended" instruction. The human did not
confirm these interactively; see DECISIONS.md D-01.

## R1 Fixtures (~20)
- About 20 seeded-defect fixtures: mostly Python and Go, plus a couple of Terraform.
- Based on real agent failure modes: unrelated code deleted, requirement silently dropped, test
  bypassing the API route, schema validation disabled to pass tests, hard-coded expected values,
  swallowed errors, secrets written to logs, over-broad IAM.
- Each fixture has: a base state (files), a diff, and a ground-truth label with the defect
  category (plus language, affected file, short description).
- A few clean control fixtures (diff with no defect) so false positives are measurable.

## R2 Runner
- Sends each diff to reviewer configs: model A, model B, and A-then-B.
- Pluggable provider adapters. API keys only from environment variables.
- Per-run cost cap (USD) that stops spending when reached; dry-run mode that makes no network
  calls and spends nothing.

## R3 Scoring
- Reviewers return structured JSON findings; the parser validates them and tolerates malformed
  output (counted, not fatal).
- Precision and recall per defect category, per reviewer config.

## R4 Report
- Markdown report: overlap and blind-spot matrix between models, cost per true catch, per-category
  precision/recall, and a chart.

## Constraints
- Python, standard library only for application code; dev tools pytest, ruff, mypy.
- `bash scripts/check.sh` must pass (ruff check, ruff format --check, mypy, pytest).
- Behavioral tests through real interfaces (real HTTP on 127.0.0.1 port 0 for adapters).
- Fixtures in Go/Terraform are data files only; they are not compiled or executed.

## R5 Harder fixtures (added after the first live run)
First live run (runs/live-2): both models caught 20/20 seeded defects, so the set cannot
discriminate between configs. Goal: add a "hard" tier where a single strong reviewer misses some
defects, keeping the original tier for comparison.
- Same 8 defect categories; each hard fixture still has exactly one seeded defect.
- Defects are subtle and buried: multi-file diffs (3-6 files, roughly 100-250 changed lines) that
  mix refactors/renames/formatting and legitimate related changes with the defect.
- Hard clean controls contain suspicious-looking but correct code (justified broad `except`,
  a wildcard in a Deny statement, legitimately expected literals in tests) to stress precision.
- Success criterion (measured, not assumed): on a live pilot, single-model recall on the hard tier
  is clearly below 100% (target roughly 40-80%) with at least some disagreement between A and B.
- Scoring and report show easy and hard tiers separately and combined.

## R6 Extra findings (added after the hard-tier pilot)
Precision/recall against the single seeded defect cannot credit real problems a reviewer finds
beyond it (e.g. the unintended ReceiptLog rename in h_py_validation_disabled_1), and it hides the
way two reviewers differ in practice (the extras). Add:
- an adjudication of every non-seeded ("extra") finding in a run as real / not_real / unclear,
  made by a model from a third family (not A's or B's), with a human-checkable sample;
- scoring and report sections that count validated extras per config and per model pair
  (unique-to-A, unique-to-B, shared), and a precision variant that counts real extras as correct;
- no change to the existing strict seeded-defect metrics.
