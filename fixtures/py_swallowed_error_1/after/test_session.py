import json

import session


def test_state_default_empty():
    assert session.STATE == {}


def test_save_state_writes_json(tmp_path):
    session.STATE["k"] = 1
    target = tmp_path / "s.json"
    session.save_state(str(target))
    assert json.loads(target.read_text()) == {"k": 1}
