import json

import pytest

from feature_config.loader import DEFAULT_ENDPOINT, load_config
from feature_config.model import FeatureFlags


def test_defaults_are_disabled() -> None:
    config = load_config(environ={})

    assert config.endpoint == DEFAULT_ENDPOINT
    assert config.api_token == ""
    assert config.features == FeatureFlags(
        {"search": False, "recommendations": False}
    )


def test_json_defaults_are_loaded(tmp_path) -> None:
    target = tmp_path / "config.json"
    target.write_text(
        json.dumps(
            {
                "endpoint": "https://service.example.invalid",
                "api_token": "EXAMPLE-NOT-A-REAL-TOKEN-0000",
                "features": {"search": True},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(target, environ={})

    assert config.endpoint == "https://service.example.invalid"
    assert config.api_token == "EXAMPLE-NOT-A-REAL-TOKEN-0000"
    assert config.features.enabled("search") is True
    assert config.features.enabled("recommendations") is False


def test_environment_overrides_file_and_adds_flags(tmp_path) -> None:
    target = tmp_path / "config.json"
    target.write_text(
        '{"endpoint": "https://old.example.invalid", "features": {}}',
        encoding="utf-8",
    )

    config = load_config(
        target,
        {
            "SERVICE_ENDPOINT": "https://new.example.invalid",
            "SERVICE_API_TOKEN": "EXAMPLE-NOT-A-REAL-TOKEN-1111",
            "SERVICE_FLAG_SEARCH": "yes",
            "SERVICE_FLAG_DARK_MODE": "on",
        },
        prefix="SERVICE_",
    )

    assert config.endpoint == "https://new.example.invalid"
    assert config.features.enabled("search") is True
    assert config.features.enabled("dark_mode") is True


@pytest.mark.parametrize("value", ["sometimes", "2", "enabled"])
def test_invalid_flag_value_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="must contain a boolean value"):
        load_config(environ={"APP_FLAG_SEARCH": value})


def test_non_object_json_is_rejected(tmp_path) -> None:
    target = tmp_path / "config.json"
    target.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_config(target, environ={})
