# Decision log

Autonomous run. Each entry: what was decided, why, and how to reverse it.

- D-01 Working agreement conflict. CLAUDE.md requires human confirmation of REQUIREMENTS.md and
  plan approval before code. The user explicitly asked for an unattended end-to-end run using
  cross-review as the gate, so I treated plan-review findings (with my assessment) as the
  approval step and logged each outcome here. Reverse: re-review plans/ and REQUIREMENTS.md.
- D-02 Work split into 4 steps (fixtures, providers+runner, scoring, report), each with its own
  plan, plan-review, check run. Cross-review of code at the end of steps 2 and 4.
- D-03 No git remote is configured (`git remote -v` is empty), so pushing is impossible. I will commit locally on `main` and report this; the user must add a remote.
  locally on a feature branch's worth of work on `main`... see D-03 updates below.
- D-04 Step-1 plan review: agreed with all 8 findings (exact 20+4 inventory, one defect per
  fixture, diff via temp git repo for root-relative paths, optional label fields for clean
  controls, header-aware diff parsing, FixtureError boundary, bounded subprocess waits, run check).
- D-05 Fixtures authored as base/ + after/ with diff.patch generated, so diffs always apply.
  meta.json (reviewer-visible task) is separate from label.json (hidden truth).
- D-06 Fixture ids contain the category name (e.g. `py_swallowed_error_1`), so the runner must
  never put the fixture id into a prompt; it uses opaque case numbers. Enforced by a runner test.
- D-07 Added `extend-exclude = ["fixtures"]` to ruff config (fixtures are code under review, not
  project code; some are deliberately bad). Config only, no new dependency.
- D-08 Go fixtures were syntax-checked with `gofmt -e` by hand (not part of check.sh). Terraform
  fixtures are unchecked (no terraform binary). Ground truth was re-read against INVENTORY.md.
- D-09 Step 1 done: check passed (ruff check, format, mypy, pytest 17). Committed locally.
