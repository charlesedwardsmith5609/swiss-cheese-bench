"""Benchmark configuration (models, prices, limits). Threading: none."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

PROVIDER_KINDS = frozenset({"anthropic", "openai"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ConfigError(Exception):
    """Invalid benchmark configuration."""


@dataclass(frozen=True)
class ModelSpec:
    key: str  # "A" or "B"
    provider: str  # anthropic | openai
    model_id: str
    usd_per_mtok_in: float
    usd_per_mtok_out: float
    api_key_env: str
    base_url: str | None = None  # None => provider default (https)


@dataclass(frozen=True)
class BenchConfig:
    models: dict[str, ModelSpec]
    max_output_tokens: int = 2000
    timeout_s: float = 120.0
    cap_usd: float = 5.0


def check_base_url(url: str) -> str:
    """https is required, except for loopback hosts (used by tests)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme == "https" and host:
        return url.rstrip("/")
    if parts.scheme == "http" and host in LOOPBACK_HOSTS:
        return url.rstrip("/")
    raise ConfigError(f"base_url must be https (http only for loopback): {url!r}")


def _num(data: dict[str, object], key: str, default: float | None = None) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"'{key}' must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ConfigError(f"'{key}' must be finite and >= 0")
    return number


def _str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"'{key}' must be a non-empty string")
    return value


def _model(key: str, data: object) -> ModelSpec:
    if not isinstance(data, dict):
        raise ConfigError(f"model {key} must be an object")
    provider = _str(data, "provider")
    if provider not in PROVIDER_KINDS:
        raise ConfigError(f"model {key}: provider must be one of {sorted(PROVIDER_KINDS)}")
    base_url = data.get("base_url")
    if base_url is not None:
        if not isinstance(base_url, str):
            raise ConfigError(f"model {key}: base_url must be a string")
        base_url = check_base_url(base_url)
    return ModelSpec(
        key=key,
        provider=provider,
        model_id=_str(data, "model_id"),
        usd_per_mtok_in=_num(data, "usd_per_mtok_in"),
        usd_per_mtok_out=_num(data, "usd_per_mtok_out"),
        api_key_env=_str(data, "api_key_env"),
        base_url=base_url,
    )


def parse_config(data: object) -> BenchConfig:
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")
    models = data.get("models")
    if not isinstance(models, dict) or set(models) != {"A", "B"}:
        raise ConfigError("'models' must be an object with exactly the keys A and B")
    max_out = _num(data, "max_output_tokens", 2000)
    if max_out < 1 or max_out != int(max_out):
        raise ConfigError("'max_output_tokens' must be a positive integer")
    timeout = _num(data, "timeout_s", 120)
    if timeout <= 0:
        raise ConfigError("'timeout_s' must be > 0")
    return BenchConfig(
        models={k: _model(k, models[k]) for k in ("A", "B")},
        max_output_tokens=int(max_out),
        timeout_s=timeout,
        cap_usd=_num(data, "cap_usd", 5.0),
    )


def load_config(path: Path) -> BenchConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    return parse_config(data)
