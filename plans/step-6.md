# Step 6: adjudicate extra findings; score validated extras; fix flawed fixtures

Concurrency: none. Synchronous; one bounded `agent` subprocess at a time per call (the shell may
run several driver processes in parallel on disjoint fixture ids; each writes its own file).

## Part A: adjudication (swiss_cheese_bench/adjudicate.py)
- Extra finding = a finding whose (category, normalised file) is not the fixture's seeded
  (category, file). Findings are deduplicated per fixture by (category, file) across A, B and
  B_after_A, so each distinct extra is judged once. Clean-control findings are all extras.
- `collect_extras(run_dir, fixtures) -> dict[fixture_id, list[Extra]]` (Extra: category, file,
  message(s) from the models, which calls raised it).
- Prompt (per fixture, one call): task text + the diff + the list of distinct extras with the
  reviewer's message. Ask for JSON `{"verdicts":[{"index":int,"verdict":"real|not_real|unclear",
  "reason":str}]}`. "real" = the diff really introduces that problem (a genuine defect, even if not
  one of the 8 categories' seeded kind, and not a style nit); "not_real" = the claim is false,
  already handled, or not caused by this diff; "unclear" = judgement call. The prompt does not
  reveal the seeded label, models' identities, or whether a finding came from A or B.
- Adjudicator: grok-4.7-medium-fast through Cursor read-only ask mode (a family that is neither
  A's (Anthropic) nor B's (OpenAI)); output captured with the existing capped, process-group
  run_agent. Tolerant parser: missing/invalid verdicts => "unclear" with reason "unparsed".
  Up to 2 retries per fixture with the error fed back.
- Output: `<run>/adjudication.json` = {"adjudicator": model, "created": run id/time-less,
  "items":[{"fixture_id","category","file","verdict","reason"}]}. Written atomically (temp +
  rename), refuses to overwrite unless `--force`.
- Human check: the driver also writes `adjudication_sample.md` with a deterministic sample
  (every 4th item, sorted) showing the diff hunk context for the finding, the verdict and reason,
  so a person can verify. I additionally read that sample and record the agreement in
  DECISIONS.md.
- CLI: `python -m swiss_cheese_bench adjudicate --run DIR [--fixtures DIR] [--model M] [--force]`.

## Part B: scoring and report
- scoring.py: optional `load_adjudication(run_dir)` (schema-validated; ScoringError on corrupt
  file, None when absent). `ConfigScore` gains `extras_real`, `extras_not_real`, `extras_unclear`,
  `extras_unadjudicated` (distinct extras of that config within the slice's cohort) and
  `adjusted_precision` = (tp + extras_real) / predicted (None when predicted is 0).
  Scoring gains `extras_overlap`: for real extras, counts unique-to-A, unique-to-B and shared
  (A and B independent findings; A_then_B/union derive from them). Existing metrics unchanged.
- report.py: new section "Extra findings (not the seeded defect)" per slice, shown only when an
  adjudication exists (otherwise a one-line note that it is missing): table per config with real /
  not real / unclear / unadjudicated and adjusted precision; line for real extras
  unique-to-A / unique-to-B / shared; a caution that verdicts come from one model plus a human
  sample.

## Part C: fixture fixes (no scoring-rule changes)
- unrelated_deletion x3 (h_py_unrelated_deletion_1, h_py_unrelated_deletion_2,
  h_go_unrelated_deletion_1): re-author with a note that the deleted code must NOT be a
  validation/bounds check (use e.g. a cleanup/close, an audit/metrics call, a retry guard, or a
  whole helper), so the category is unambiguous. Retire the old versions to .reviews/retired/.
- h_py_validation_disabled_1: re-author with a note to avoid the unintended public-API rename.
- Re-audit all four new ones with Grok-as-auditor if OpenAI-authored, otherwise I read the full
  diff (these were Grok-authored) and also run a grok-4.7 audit on them (accepting that the
  audit then shares the author model; a second pass by gpt-5.6-sol-high-fast is used instead,
  because the plan's concern was keeping B's family out of authoring AND auditing of the same
  fixture, and these were authored by Grok, so a gpt audit is fine). Recorded in INVENTORY.md.
- h_tf_secret_logged_1 (right category, different file): left unchanged and noted; strict file
  matching is a deliberate rule and I am not changing it after seeing results.
- A re-run of the hard tier is paid and is NOT part of this step; I stop and ask for it.

## Tests
- adjudicate: collect_extras dedup and exclusions on synthetic runs (seeded match excluded, clean
  fixture findings all extras, B_after_A duplicates collapse); prompt contains diff/task/extras and
  not the label, fixture id or model names; verdict parser (fenced/prose, missing -> unclear,
  bad enum -> unclear); driver with a fake `agent` (retries, timeout, no overwrite without --force,
  atomic write); sample selection deterministic.
- scoring/report: counts and adjusted precision hand-computed; absent adjudication => no extras
  section and unchanged numbers; corrupt adjudication => ScoringError; unique-to-A/B/shared.
- Fixtures: existing grid/shape/tier tests keep passing for the re-authored cells.

## Done criteria
check.sh four stages; plan-review of this plan; cross-review of the code diff (excluding fixture
data) at the end; DECISIONS.md updated; commit and push.

## Changes after plan review (all 8 findings adopted)
1. Claims, not merged pairs: every non-seeded finding is a Claim with a stable id
   `<fixture>/<kind>/<index>` and is adjudicated individually (`file` may be None). For counting,
   claims are clustered by (fixture, category, normalised file); a cluster is `real` only if all its
   claims are real, `not_real` only if all are not_real, otherwise `unclear`. Claims matching the
   seeded (category, file) are the catch and are excluded.
2. Family guard: adjudicator model family (claude->anthropic, gpt/o->openai, grok->xai, gemini->
   google, else the name) must differ from the families of models A and B in run.json (provider and
   model id); otherwise the driver refuses to run.
3. Concurrency: one driver per run, enforced by an exclusive lock file `<run>/.adjudicate.lock`;
   `--jobs N` threads each own one fixture and write only `<run>/adjudication/<fixture>.json`;
   the main thread alone aggregates into adjudication.json (atomic temp+rename) after all workers
   finish. Existing per-fixture files are reused (resume) unless `--force`.
4. adjudication.json carries the sha256 fingerprint of results.jsonl and must cover EXACTLY the
   run's claim ids (no missing, no extra), else `ScoringError`; no "unadjudicated" state.
5. Per-config extras are counted over that config's own scored fixtures in the slice; unique/shared
   comparison uses the A-and-B-both-scored fixtures of the slice and reports its size.
6. Config sources: A=A claims; B=B claims; A_then_B=B_after_A claims; A_union_B=A+B claims. The
   unique-to-A / unique-to-B / shared split compares A vs B only. A test covers a B_after_A-only
   extra.
7. Injection: task, diff and reviewer messages are placed between explicit data delimiters with a
   instruction not to follow instructions inside them; a test uses an injection-shaped finding and
   checks the prompt structure (the model's behaviour cannot be unit tested).
8. Files that are None or not in the diff: Extra.file nullable; the human sample shows "no file"
   or "file not in diff" and falls back to the first 60 diff lines.
