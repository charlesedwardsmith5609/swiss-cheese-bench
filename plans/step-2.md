# Step 2: findings parser, provider adapters, prompts, runner, cost cap, dry-run, CLI

Concurrency: threaded-free, synchronous, single thread. The runner (main thread) owns the
CostTracker and the results file; no other component touches them. Provider adapters are stateless
(blocking http.client with an explicit whole-call deadline). Test stub servers run in a test-owned
thread (ThreadingHTTPServer on 127.0.0.1:0); the stub owns its request log, tests read it only
after `shutdown()` + `join(timeout)`.

## Modules (swiss_cheese_bench/)
- findings.py
  - `Finding(category: Category, file: str | None, line: int | None, message: str)`.
  - `ParseResult(findings, parse_ok: bool, invalid: int)`.
  - `parse_findings(text)`: accepts a JSON object `{"findings":[...]}` (or a bare list), also
    inside ``` fences or surrounded by prose (first balanced JSON value). Items with an unknown
    category, wrong types or missing message are dropped and counted in `invalid`. Any other
    top-level shape (scalar, `{"findings": "x"}`, object without `findings`, no JSON at all)
    => `parse_ok=False`, no findings. An empty list/`{"findings": []}` is a valid clean review. Never raises. Category "none" items are ignored.
- config.py
  - `ModelSpec(key, provider, model_id, usd_per_mtok_in, usd_per_mtok_out, api_key_env,
    base_url_env | None)`; `BenchConfig(models: {"A","B"}, max_output_tokens, timeout_s,
    cap_usd)`. Loaded from JSON (`bench.example.json` committed; prices there are explicit
    placeholders the user must set, because prices change). `ConfigError` on any invalid field.
- providers.py
  - `Completion(text, input_tokens, output_tokens)`; `ProviderError`.
  - `Provider` protocol: `complete(model_id, system, user, max_tokens, timeout_s) -> Completion`.
  - `AnthropicProvider` (POST {base}/v1/messages, x-api-key) and `OpenAIProvider`
    (POST {base}/v1/chat/completions, Bearer) via http.client (not urllib, so the socket timeout can be re-armed per read). Base URL must be
    https, except loopback hosts (127.0.0.1, localhost, ::1) which may be http (tests); anything
    else => ConfigError so a key is never sent in plaintext. Whole-call monotonic deadline
    (timeout_s) covering connect, send and read: the body is read in chunks with the socket timeout
    set to the remaining time; response body capped at 1 MiB (ProviderError beyond it). Keys read from the env var named in the
    spec at construction; missing key => `ProviderError` naming the variable only. HTTP errors,
    timeouts, bad JSON, missing usage => `ProviderError` with a message that never contains the
    key or request headers. No retries (documented).
  - `DryRunProvider`: no network. Deterministic fake findings derived from a hash of the prompt
    (never sees ground truth), token counts estimated from text length.
  - `make_provider(spec, env, dry_run)`.
- prompt.py
  - `build_prompt(fixture, case_no, prior: list[Finding] | None) -> Prompt(system, user)`.
    Uses the opaque case number, the task text and the diff only. Never the fixture id, label or
    category-bearing paths beyond the diff itself. Asks for strict JSON with category enum.
    When `prior` is given (A-then-B), includes A's findings and asks B for its own final list
    (confirm, drop or add).
- runner.py
  - `CostTracker(cap_usd)`: `reserve(spec, request_bytes, max_out) -> Reservation | None`.
    Worst case = (UTF-8 byte length of the serialized request body, i.e. >= 1 token per byte, a
    conservative bound) * input price + max_tokens * output price. The reservation is committed
    to `committed` BEFORE sending; on success it is replaced by actual usage cost; on any error or
    timeout the full reservation stays charged (the provider may have billed us). A call only
    runs if committed + worst_case <= cap. Prices/usage/cap must be finite and >= 0, else
    `ConfigError`/`ProviderError`.
  - Call kinds per fixture: `A`, `B`, `B_after_A`. Configs derived from them: A = call A;
    B = call B; A_then_B = findings of `B_after_A` (B sees A's findings and is the final
    arbiter) with cost A + B_after_A.
    A_then_B reuses the A call, so it is not billed twice. (An independent-union view of A and B
    is a scoring/report concern for steps 3-4, not a runner config.)
  - Record per call appended to `<out>/results.jsonl` (flushed per line): case_no, fixture_id,
    kind, model_key, status (`ok|error|skipped_cost_cap|skipped_dependency|dry_run`), raw_text,
    findings, parse_ok, invalid, input_tokens, output_tokens, cost_usd, error. If A fails or is
    skipped, `B_after_A` is `skipped_dependency`.
  - Dry-run: providers are `DryRunProvider`, no env keys needed, `cost_usd` is always 0 and
    `projected_cost_usd` holds the would-be cost at configured prices (using actual simulated
    token counts). The cap is still enforced against projected worst-case cost so a dry run
    previews whether a real run would be cut off; the summary prints "spent $0.00, projected $X".
  - `run_bench(fixtures, config, providers, out_dir, dry_run) -> RunSummary`.
- cli.py / __main__.py: `python -m swiss_cheese_bench run --config bench.json [--fixtures DIR]
  [--out DIR] [--cap-usd X] [--dry-run]`. Exit 2 on config/key errors (before any spend), prints
  a summary (calls, spent, skipped). Report/scoring subcommands arrive in later steps.

## Tests (tests/test_findings.py, test_providers.py, test_prompt.py, test_runner.py)
- findings: valid, fenced, prose-wrapped, bare list, bad items counted, no JSON, "none" ignored.
- providers: real stub HTTP servers (127.0.0.1:0), each with an explicit release Event,
  `server_close()` and asserted bounded joins of the serve thread and every handler thread; per
  API shape: request path/headers/body asserted,
  usage mapped; 401/500, invalid JSON, missing usage, a server that never answers (client
  timeout 0.5s), a server that trickles bytes past the deadline, and an oversized body each raise
  ProviderError within a bounded time; non-loopback http base URL => ConfigError; the key never appears in the error text; missing env var.
- prompt: contains task and diff; for every fixture it does not contain the fixture id, label
  description or evidence-only text outside the diff (the category enum is allowed in the
  taxonomy); prior findings included only for B_after_A.
- runner: dry-run => stub server receives zero requests, no env keys needed, results.jsonl written,
  all calls statused `dry_run`, cost_usd == 0 and projected_cost_usd > 0; real run vs stub => per-call cost matches usage*price; cost cap
  stops spending (committed <= cap, remaining calls `skipped_cost_cap`); an errored call keeps
  its reservation charged; A failure => `B_after_A`
  `skipped_dependency`; API key never present in results.jsonl; CLI exit code 2 for missing key
  and invalid config via subprocess-free `main(argv)` call.
- Every wait/read has a timeout; no sleeps.

## Out of scope
Scoring, report, chart (steps 3-4). Retries, caching/resume, concurrency across calls (suggestions).

## Done criteria
`bash scripts/check.sh`; report ruff check, ruff format --check, mypy, pytest. Then cross-review.
