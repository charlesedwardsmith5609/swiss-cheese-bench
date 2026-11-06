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
