import os
from collections.abc import Mapping

from feature_config.model import FeatureSettings, RuntimeConfig

DEFAULT_ENDPOINT = "https://api.example.invalid"


def _enabled(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes"}


def load_config(environ: Mapping[str, str] | None = None) -> RuntimeConfig:
    source = os.environ if environ is None else environ
    endpoint = source.get("APP_ENDPOINT", DEFAULT_ENDPOINT)
    api_token = source.get("APP_API_TOKEN", "")
    features = FeatureSettings(
        search=_enabled(source.get("APP_SEARCH_ENABLED")),
        recommendations=_enabled(source.get("APP_RECOMMENDATIONS_ENABLED")),
    )
    return RuntimeConfig(
        endpoint=endpoint,
        api_token=api_token,
        features=features,
    )
