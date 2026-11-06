# swiss-cheese-bench

Does pairing two different models as code reviewers catch more agent-introduced defects than
either alone? 24 small fixtures (20 seeded defects, 4 clean controls; Python, Go, Terraform)
cover eight failure modes. Standard library only.

    cp bench.example.json bench.json      # set model ids AND real prices; keys come from env vars
    python -m swiss_cheese_bench run --config bench.json --dry-run     # no network, nothing spent
    python -m swiss_cheese_bench run --config bench.json --cap-usd 2   # live; stops at the cap
    python -m swiss_cheese_bench report --run runs/latest --out report.md   # + report.chart.svg

Configs compared: A, B, A then B (B sees A's findings), and A ∪ B (independent). See
`fixtures/INVENTORY.md` for ground truth, `DECISIONS.md` for design decisions and known limits,
and `examples/dry-run-report.md` for a SIMULATED example report (fake reviewer, not real results).
Dev: `bash scripts/check.sh`.
