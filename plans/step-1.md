# Step 1: fixture format, loader, validator, and 24 fixtures

Concurrency: none (pure synchronous file I/O, single thread). No shared state.

## Layout (data)
fixtures/<id>/
  meta.json    visible to reviewers: {"id","language","task"}  (task = what the agent was asked)
  label.json   hidden ground truth: {"category","file","description","evidence"}
  base/        the repo state before the change
  after/       the repo state after the agent's change
  diff.patch   unified diff base->after (-U8), generated from base/after, committed

Authoring from base+after and generating the diff guarantees the diff is exactly applicable.

## Categories (enum `Category`, str values)
unrelated_deletion, dropped_requirement, test_bypasses_route, validation_disabled,
hardcoded_expected, swallowed_error, secret_logged, overbroad_iam; clean controls use "none".

## Fixture set (24 = exactly 20 defective + 4 clean; each defective has exactly ONE defect)
Inventory (category x language), asserted exactly in tests/test_fixtures.py:
- unrelated_deletion: py, go
- dropped_requirement: py, go, go
- test_bypasses_route: py, go
- validation_disabled: py, go
- hardcoded_expected: py, go, go
- swallowed_error: py, py, go
- secret_logged: py, go, terraform (sensitive value exposed in an un-sensitive output)
- overbroad_iam: terraform, terraform
Totals: python 8, go 9, terraform 3 defective. Clean controls (category "none"): py, go, go, tf.
Each diff mixes a legitimate change with the seeded defect so it is not trivially obvious.
`fixtures/INVENTORY.md` lists id, category, language, affected path and a one-line rationale per
fixture; I re-read every base/after/label triple against it before finishing (the human should
spot-check it; a syntactic test cannot prove ground truth).

## Code (swiss_cheese_bench/fixtures.py)
- `Category` (StrEnum incl. NONE="none"), `Label` (frozen: category, file: str|None,
  description: str|None, evidence: str|None; for NONE all three optional fields must be absent,
  for any other category all three are required), `Fixture` (frozen: id, language, task, label,
  diff, base_dir, after_dir).
- `load_fixtures(root: Path) -> list[Fixture]` sorted by id. Error boundary: every failure
  (missing file, bad encoding, malformed JSON, missing/wrong-typed field, unknown category,
  language) is wrapped as `FixtureError` naming the fixture and file.
- `make_diff(base_dir, after_dir) -> str`: in a TemporaryDirectory, `git init`, commit base,
  replace the work tree with after, `git diff -U8 --no-color` => root-relative `a/x` / `b/x`
  headers. All subprocess calls have timeouts (git is a system tool, not a Python dependency).
- `python -m swiss_cheese_bench.fixtures regen [root]` rewrites diff.patch files.
- `parse_diff(text)`: minimal parser returning per-file lists of added and removed hunk lines
  (headers `---`/`+++` excluded) and the set of changed paths.
- `validate(fixture)`: label.file exactly equals a changed path; evidence is a substring of an
  added/removed hunk line of that file; clean controls have a non-empty diff.

## Tests (tests/test_fixtures.py)
- every fixture loads; ids unique and equal to dir names;
- committed diff.patch equals freshly generated diff (no drift);
- `git apply` (timeout 30s, tmp dir cleaned via context manager) of diff.patch onto a copy of
  base/ reproduces after/ byte-for-byte;
- label evidence/file present in diff; category and language coverage counts as above;
- bad fixtures (tmp_path): missing meta/label, malformed JSON, wrong types, unknown category,
  evidence only in a header, clean control with defect fields, defective without them -> FixtureError;
- exact inventory (category x language counts and totals) matches the table above.
- reviewer-visible text (meta.json) never contains the category name or label description.

## Out of scope
Provider calls, runner, scoring, report.

## Done criteria
Run `bash scripts/check.sh` last; report ruff check, ruff format --check, mypy, pytest.
