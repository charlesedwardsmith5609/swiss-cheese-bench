from __future__ import annotations

import json
import stat
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from swiss_cheese_bench import authoring
from swiss_cheese_bench.authoring import (
    CELL_BY_ID,
    CELLS,
    AuthoringError,
    Cell,
    materialize,
    parse_authored,
    run_agent,
    run_cell,
)
from swiss_cheese_bench.fixtures import Category, load_fixtures

CELL = CELL_BY_ID["h_py_swallowed_error_1"]
CLEAN = CELL_BY_ID["h_clean_py_1"]


def reply_dict(nfiles: int = 3, lines: int = 40, **over: Any) -> dict[str, Any]:
    base = {f"pkg/m{i}.py": "x = 1\n" for i in range(nfiles)}
    after = {
        f"pkg/m{i}.py": "x = 1\n" + "".join(f"v{j} = {j}\n" for j in range(lines))
        for i in range(nfiles)
    }
    after["pkg/m0.py"] += "result = swallow()  # EVIDENCE-LINE\n"
    data: dict[str, Any] = {
        "task": "Add the feature to the service and keep the tests passing.",
        "base": base,
        "after": after,
        "label": {"file": "pkg/m0.py", "description": "swallows", "evidence": "EVIDENCE-LINE"},
        "why_hard": "buried",
    }
    data.update(over)
    return data


def as_text(data: dict[str, Any], fenced: bool = True) -> str:
    body = json.dumps(data)
    return f"Here you go:\n```json\n{body}\n```\n" if fenced else body


def test_cells_grid_is_exact() -> None:
    assert len(CELLS) == 32 and len({c.id for c in CELLS}) == 32
    defective = [c for c in CELLS if c.category is not Category.NONE]
    assert Counter(c.language for c in defective) == {"python": 10, "go": 10, "terraform": 4}
    per_cat = Counter(str(c.category) for c in defective)
    assert set(per_cat.values()) == {3} and len(per_cat) == 8
    clean = [c for c in CELLS if c.category is Category.NONE]
    assert Counter(c.language for c in clean) == {"python": 3, "go": 3, "terraform": 2}
    assert {c.author for c in CELLS} == {"grok", "gpt"}
    assert {
        c.author for c in defective if str(c.category) in ("swallowed_error", "overbroad_iam")
    } == {"gpt"}
    assert all(c.id.startswith("h_") for c in CELLS)


def test_parse_accepts_fenced_and_plain() -> None:
    a = parse_authored(as_text(reply_dict()), CELL)
    assert a.file == "pkg/m0.py" and a.evidence == "EVIDENCE-LINE" and len(a.after) == 3
    assert parse_authored(as_text(reply_dict(), fenced=False), CELL).task == a.task


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["base"].update({"../evil.py": "x"}),
        lambda d: d["base"].update({"/abs.py": "x"}),
        lambda d: d["base"].update({".hidden/a.py": "x"}),
        lambda d: d["base"].update({".git/config.py": "x"}),
        lambda d: d["base"].update({"C:/x.py": "x"}),
        lambda d: d["base"].update({"a\\b.py": "x"}),
        lambda d: d["base"].update({"bin.exe": "x"}),
        lambda d: d["base"].update({"big.py": "x" * (64 * 1024 + 1)}),
        lambda d: d["base"].update({"crlf.py": "a\r\nb\n"}),
        lambda d: d.update(base={f"f{i}.py": "x" for i in range(9)}),
        lambda d: d.update(base={}),
        lambda d: d.pop("task"),
        lambda d: d.update(task="This is a swallowed_error case"),
        lambda d: d.update(task="a swallowed error somewhere"),
        lambda d: d.update(label={}),
        lambda d: d["label"].pop("evidence"),
        lambda d: d.update(label="nope"),
        lambda d: d["after"].update({"n.py": 5}),
    ],
)
def test_parse_rejects_bad_replies(mutate: Any) -> None:
    data = reply_dict()
    mutate(data)
    with pytest.raises(AuthoringError):
        parse_authored(as_text(data), CELL)


def test_parse_rejects_non_json_and_clean_with_label() -> None:
    for text in ("", "no json", "[1,2]", "{broken"):
        with pytest.raises(AuthoringError):
            parse_authored(text, CELL)
    with pytest.raises(AuthoringError):
        parse_authored(as_text(reply_dict()), CLEAN)  # clean control must have empty label
    ok = reply_dict(label={})
    assert parse_authored(as_text(ok), CLEAN).file is None


def test_cell_overrides_model_supplied_identity(tmp_path: Path) -> None:
    data = reply_dict(id="evil", category="none", tier="easy")
    data["label"]["category"] = "none"
    path = materialize(parse_authored(as_text(data), CELL), tmp_path, "m")
    fx = load_fixtures(tmp_path)[0]
    assert path.name == CELL.id and fx.id == CELL.id
    assert str(fx.label.category) == "swallowed_error" and fx.tier == "hard"


def test_materialize_layout_and_load(tmp_path: Path) -> None:
    materialize(parse_authored(as_text(reply_dict()), CELL), tmp_path, "model-x")
    (fx,) = load_fixtures(tmp_path)
    assert fx.language == "python" and fx.tier == "hard"
    label = json.loads((tmp_path / CELL.id / "label.json").read_text())
    assert label["author"] == "model-x" and label["why_hard"] == "buried"
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]


def test_materialize_refuses_existing_and_cleans_up_on_failure(tmp_path: Path) -> None:
    a = parse_authored(as_text(reply_dict()), CELL)
    materialize(a, tmp_path)
    with pytest.raises(AuthoringError, match="already exists"):
        materialize(a, tmp_path)
    assert (tmp_path / CELL.id / "meta.json").exists()  # original untouched
    other = Cell("h_py_x", Category.SWALLOWED_ERROR, "python", "gpt", "t")
    small = parse_authored(as_text(reply_dict(lines=2)), other)
    with pytest.raises(AuthoringError, match="added\\+removed lines"):
        materialize(small, tmp_path)
    two_files = parse_authored(as_text(reply_dict(nfiles=2, lines=60)), other)
    with pytest.raises(AuthoringError, match="files"):
        materialize(two_files, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [CELL.id]  # no partial fixture/stage dir


def test_materialize_rejects_evidence_outside_diff(tmp_path: Path) -> None:
    data = reply_dict()
    data["label"]["evidence"] = "NOT-IN-DIFF"
    with pytest.raises(AuthoringError):
        materialize(parse_authored(as_text(data), CELL), tmp_path)
    assert list(tmp_path.iterdir()) == []


# ---- the agent call (a fake `agent` executable; no Cursor, no network)


def fake_agent(tmp: Path, body: str) -> str:
    script = tmp / "fake_agent.py"
    script.write_text(f"#!{sys.executable}\nimport sys, json, os, time\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def test_run_agent_passes_arguments_and_returns_reply(tmp_path: Path) -> None:
    log = tmp_path / "args.json"
    agent = fake_agent(
        tmp_path, f"json.dump(sys.argv[1:], open({str(log)!r}, 'w'))\nprint('REPLY')"
    )
    out = run_agent("PROMPT TEXT; $(rm -rf /)", "some-model", tmp_path / "w", agent, 20)
    assert out.strip() == "REPLY"
    args = json.loads(log.read_text())
    assert args[-1] == "PROMPT TEXT; $(rm -rf /)"  # one argv element, never a shell string
    assert args[args.index("--model") + 1] == "some-model" and "--mode=ask" in args


def test_run_agent_timeout_size_cap_and_failure(tmp_path: Path) -> None:
    slow = fake_agent(tmp_path, "time.sleep(60)")
    with pytest.raises(AuthoringError, match="timed out"):
        run_agent("p", "m", tmp_path / "w", slow, timeout_s=1)
    flood = fake_agent(
        tmp_path, "sys.stdout.write('x' * 2_000_000); sys.stdout.flush(); time.sleep(30)"
    )
    with pytest.raises(AuthoringError, match="size cap"):
        run_agent("p", "m", tmp_path / "w", flood, timeout_s=20, max_bytes=100_000)
    bad = fake_agent(tmp_path, "sys.exit(3)")
    with pytest.raises(AuthoringError, match="status 3"):
        run_agent("p", "m", tmp_path / "w", bad, timeout_s=20)
    with pytest.raises(AuthoringError, match="cannot start"):
        run_agent("p", "m", tmp_path / "w", str(tmp_path / "missing-binary"), timeout_s=5)


def test_run_cell_retries_with_the_rejection_reason(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    good.write_text(as_text(reply_dict()))
    bad = tmp_path / "bad.txt"
    bad.write_text("not json at all")
    state = tmp_path / "state"
    prompts = tmp_path / "prompts.jsonl"
    agent = fake_agent(
        tmp_path,
        f"""
n = int(open({str(state)!r}).read()) if os.path.exists({str(state)!r}) else 0
open({str(state)!r}, 'w').write(str(n + 1))
open({str(prompts)!r}, 'a').write(json.dumps(sys.argv[-1]) + '\\n')
print(open({str(good)!r} if n >= 1 else {str(bad)!r}).read())
""",
    )
    root = tmp_path / "fx"
    path = run_cell(CELL, root, "EXAMPLE", tmp_path / "w", agent_bin=agent, timeout_s=30)
    assert path == root / CELL.id
    sent = [json.loads(x) for x in prompts.read_text().splitlines()]
    assert len(sent) == 2 and "was rejected" not in sent[0] and "no JSON object" in sent[1]
    assert [p.name for p in root.iterdir()] == [CELL.id]


def test_run_cell_gives_up_after_retries_and_leaves_nothing(tmp_path: Path) -> None:
    agent = fake_agent(tmp_path, "print('nope')")
    root = tmp_path / "fx"
    with pytest.raises(AuthoringError, match="gave up"):
        run_cell(CELL, root, "EX", tmp_path / "w", agent_bin=agent, timeout_s=30)
    assert not root.exists() or list(root.iterdir()) == []


def test_example_text_and_prompt_have_no_ground_truth_leak_for_the_new_fixture() -> None:
    example = authoring.example_text(Path(__file__).resolve().parent.parent / "fixtures")
    prompt = authoring.build_prompt(CELL, example)
    assert "swallowed_error" in prompt  # the author is told the hidden category (it must write it)
    assert str(authoring.MAX_CHANGED_LINES) in prompt and "Language: python" in prompt
    assert "was rejected" in authoring.build_prompt(CELL, example, "bad thing")


def test_prompt_includes_audit_note_only_when_given() -> None:
    plain = authoring.build_prompt(CELL, "EX")
    noted = authoring.build_prompt(CELL, "EX", note="FIFO order is wrong")
    assert "audit of an earlier attempt" not in plain
    assert "FIFO order is wrong" in noted and "exactly the one seeded defect" in noted
