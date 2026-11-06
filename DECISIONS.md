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
- D-10 Step-2 plan review: agreed with 7 of 8. Adopted: pessimistic byte-based cost reservation
  that stays charged on error; http.client with whole-call deadline and 1 MiB body cap; https
  required except loopback; dry-run cost_usd=0 with separate projected cost; strict findings
  top-level schema; prompt test allows the category taxonomy; test-server cleanup via events and
  bounded joins.
- D-11 Disagreed (partly) on removing A_union_B: removed from the runner, but I will compute an
  independent-union view in scoring/report (steps 3-4), since "does pairing beat either alone"
  needs it. No extra API calls.
- D-12 No temperature parameter is sent to any provider (some current models reject it), so runs
  are not strictly reproducible. No retries. Results are one sample per (fixture, call).
- D-13 Step-2 cross-review (diff truncated at 60k chars by the script, so the tail of the test
  files was probably not reviewed). Agreed with all 6 findings and fixed them: watchdog timer
  that shuts the socket down at the whole-call deadline (covers header trickling; this adds one
  short-lived timer thread per call that only calls socket.shutdown, so the runner is still
  single-threaded in the sense of state ownership); API key stripped and rejected if non-printable,
  and transport/header errors never echo exception text; dry-run keeps worst-case reservations
  committed so its cap preview matches a live run; token counts bounded to 1e9; parser catches
  ValueError (int-digit limit); fixture count/size limits.
- D-14 Test API keys are obviously fake strings; the first one tripped gitleaks in the review
  script (correctly refusing to send), so they were renamed to low-entropy placeholders.
- D-15 Known limit: connect uses the socket timeout and is not covered by the watchdog's abort
  (socket does not exist yet); worst case a call takes ~2x timeout_s. Left as is.
- D-16 Step 2 done: check passed (79 tests). Committed locally.
- D-17 Step-3 plan review: agreed with all 7. Notable calls: (a) a finding with no file is a false
  positive, never a catch (stricter than my first draft); (b) all comparisons use a common cohort
  of fixtures where every config was scored; (c) cost per true catch uses ALL incurred cost
  including failed-call reservations (conservative, may overstate); (d) runs must be finalized and
  complete or scoring refuses them.
- D-18 Parse failure counts as a miss (the model failed to review); API error / cap skip is
  unscored. Findings are deduped per (category, file) per fixture.
- D-19 Step 3 done (scoring.py). Overlap rows report `a_then_b_caught` without a separate
  "scored" count, because all comparisons use the common cohort, so the denominator is always the
  bucket size. check passed (102 tests). No cross-review at this step (reserved for the end of
  step 4, which covers the whole diff since step 2).
