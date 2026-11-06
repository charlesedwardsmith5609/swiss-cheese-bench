import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from feature_config.model import FeatureFlags, RuntimeConfig

DEFAULT_ENDPOINT = "https://api.example.invalid"
DEFAULT_FLAGS = {
    "search": False,
    "recommendations": False,
}

logger = logging.getLogger(__name__)


def _parse_boolean(value: str, *, variable: str) -> bool:
    """Parse a conventional environment-variable boolean."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{variable} must contain a boolean value")


def _read_defaults(path: Path | None) -> tuple[str, str, dict[str, bool]]:
    if path is None:
        return DEFAULT_ENDPOINT, "", dict(DEFAULT_FLAGS)

    with path.open(encoding="utf-8") as stream:
        document: Any = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("configuration file must contain a JSON object")

    endpoint = document.get("endpoint", DEFAULT_ENDPOINT)
    api_token = document.get("api_token", "")
    raw_flags = document.get("features", {})
    if not isinstance(endpoint, str) or not isinstance(api_token, str):
        raise ValueError("endpoint and api_token must be strings")
    if not isinstance(raw_flags, dict):
        raise ValueError("features must be a JSON object")
    if not all(
        isinstance(name, str) and isinstance(value, bool)
        for name, value in raw_flags.items()
    ):
        raise ValueError("feature names must be strings with boolean values")

    flags = dict(DEFAULT_FLAGS)
    flags.update(raw_flags)
    return endpoint, api_token, flags


def load_config(
    path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    prefix: str = "APP_",
) -> RuntimeConfig:
    """Load JSON defaults and apply prefixed environment overrides."""
    source = os.environ if environ is None else environ
    config_path = None if path is None else Path(path)
    endpoint, api_token, flags = _read_defaults(config_path)

    endpoint = source.get(f"{prefix}ENDPOINT", endpoint)
    api_token = source.get(f"{prefix}API_TOKEN", api_token)
    flag_prefix = f"{prefix}FLAG_"
    for variable, value in source.items():
        if not variable.startswith(flag_prefix):
            continue
        name = variable.removeprefix(flag_prefix).strip().lower()
        if not name:
            raise ValueError("feature flag environment variable has no name")
        flags[name] = _parse_boolean(value, variable=variable)

    config = RuntimeConfig(
        endpoint=endpoint,
        api_token=api_token,
        features=FeatureFlags(flags),
    )
    logger.info("Loaded runtime configuration: %r", config)
    return config
