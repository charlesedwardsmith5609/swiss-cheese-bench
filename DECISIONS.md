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
- D-20 Step-4 plan review: agreed with 5 of 6. Disagreed with "wait for human approval before
  applying cross-review fixes": the user asked for an unattended run, so I apply findings I agree
  with, rerun check.sh, and log them here. Adopted: projected-cost labels in dry run, per-report
  chart filename, atomic two-file write with exit 2 on OSError, numeric chart assertions,
  tolerant metadata getters.
- D-21 Step-4 cross-review (diff vs HEAD~2, truncated at 60k of 129k chars: most of the diff,
  notably fixtures, was NOT seen). Agreed and fixed: JSON ValueError in provider responses;
  connect before send plus expiry check so a slow connect cannot be followed by a late paid
  request; size limits on meta/label JSON and results.jsonl; lazy candidate scan; reject rows
  with parse_ok=false but findings; test calls to timeout paths run in bounded worker threads.
- D-22 Not fixed (accepted limits): DNS resolution is not interruptible by the watchdog (a
  stalled resolver could hang a run; fix would be a resolver thread); report writes are two
  renames, chart first and Markdown last, not a single atomic step; results.jsonl is still read
  fully in memory up to its 512 MiB cap.
- D-23 `examples/dry-run-report.md` is committed as a demo and is loudly labelled SIMULATED.
  bench.example.json uses PLACEHOLDER prices and an unset OpenAI model id on purpose; I did not
  assume current prices. The first live run needs a real bench.json.
- D-24 NOT DONE: no live run was made (no keys used, nothing spent), so there are no real
  results.
- D-25 Remote created later at the user's request: https://github.com/charlesedwardsmith5609/swiss-cheese-bench
  (created private, pushed `main`, then made public at the user's request). This supersedes the
  earlier "no remote / push impossible" notes in D-03 and D-24.
- D-26 Step 5 (hard fixtures): at the user's request fixtures are authored through the Cursor CLI
  (read-only ask mode) with grok-4.7-xhigh and gpt-5.6-sol-xhigh, split by category, excluding
  Claude models (model A's family). Plan review findings (6) incorporated as assessed. Awaiting
  user approval before any code or paid call.
- D-27 Step 5 approved by the user with all seven second-review changes: acceptance band 40-90%
  single-model hard-tier recall for BOTH models plus an A/B disagreement; Grok (not OpenAI) audits
  OpenAI-authored fixtures, Grok-authored ones audited by me/user, pilot labelled in-sample;
  `verify=False` dropped from validation_disabled; per-slice cost attribution; transactional
  materialization; 1 MiB reply cap; test assertion allows .reviews/authoring/.
- D-28 Authoring models: xhigh (grok-4.7-xhigh, gpt-5.6-sol-xhigh) and grok-4.7-high produced no
  reply within 15 min on the full fixture prompt (the CLI only emits at the end; reasoning runs
  very long). Used grok-4.7-medium-fast and gpt-5.6-sol-high-fast instead (both finished a cell in
  ~12 min), 6 cells in parallel, per-call timeout raised to 30 min. This is below the "most
  advanced" setting you asked for; quality is covered by the audit gate.
- D-29 Hard-tier fixtures authored (32). Audit: Grok audited the 16 OpenAI-authored fixtures
  without seeing labels. Clean controls came back NONE. Two defective fixtures
  (h_go_hardcoded_expected_1, h_py_hardcoded_expected_1) were flagged for a second, unintended
  defect (FIFO ordering requirement; ignored revoke() result); both were re-authored with the
  audit feedback and re-audited: now exactly the seeded defect. h_tf_overbroad_iam_1 was flagged
  for noncurrent-version retention and missing schedule tags; I judged those not defects and kept
  it (flagged in INVENTORY.md for your spot-check).
- D-30 The 16 Grok-authored fixtures had NO model audit (per plan). I read 9 in full and checked
  only labels and evidence lines for the other 7 (h_go_test_bypasses_route_2,
  h_go_validation_disabled_1, h_py_unrelated_deletion_1/2, h_py_validation_disabled_1/2,
  h_clean_tf_1). Those 7 are the least verified: please spot-check them before trusting results.
  Possible non-category extras noticed: h_go_unrelated_deletion_1 lets the caller supply the audit
  actor (spoofable); judged outside the 8 categories.
- D-31 Authoring settings were medium-fast/high-fast, not xhigh (see D-28). Fixtures were authored
  by Grok and OpenAI models, so family effects remain possible; the first hard-tier pilot is
  in-sample calibration.
