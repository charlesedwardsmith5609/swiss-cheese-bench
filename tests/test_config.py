from __future__ import annotations

import json
from pathlib import Path

import pytest

from swiss_cheese_bench.config import ConfigError, load_config, parse_config

EXAMPLE = Path(__file__).resolve().parent.parent / "bench.example.json"


def _good() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_config_loads() -> None:
    cfg = load_config(EXAMPLE)
    assert set(cfg.models) == {"A", "B"} and cfg.cap_usd > 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("models"),
        lambda d: d["models"].pop("B"),
        lambda d: d["models"]["A"].update(provider="nope"),
        lambda d: d["models"]["A"].update(usd_per_mtok_in=-1),
        lambda d: d["models"]["A"].update(usd_per_mtok_out="x"),
        lambda d: d["models"]["A"].update(usd_per_mtok_in=True),
        lambda d: d["models"]["A"].update(api_key_env=""),
        lambda d: d["models"]["A"].update(base_url="http://example.com"),
        lambda d: d.update(cap_usd=float("nan")),
        lambda d: d.update(cap_usd=-1),
        lambda d: d.update(max_output_tokens=0),
        lambda d: d.update(timeout_s=0),
    ],
)
def test_invalid_config_rejected(mutate: object) -> None:
    data = _good()
    mutate(data)  # type: ignore[operator]
    with pytest.raises(ConfigError):
        parse_config(data)


def test_unreadable_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)
