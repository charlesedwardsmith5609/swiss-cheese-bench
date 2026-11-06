from feature_config.loader import DEFAULT_ENDPOINT, load_config
from feature_config.model import FeatureSettings


def test_defaults_are_disabled() -> None:
    config = load_config({})

    assert config.endpoint == DEFAULT_ENDPOINT
    assert config.api_token == ""
    assert config.features == FeatureSettings()


def test_environment_overrides_configuration() -> None:
    config = load_config(
        {
            "APP_ENDPOINT": "https://service.example.invalid",
            "APP_API_TOKEN": "EXAMPLE-NOT-A-REAL-TOKEN-0000",
            "APP_SEARCH_ENABLED": "true",
            "APP_RECOMMENDATIONS_ENABLED": "1",
        }
    )

    assert config.endpoint == "https://service.example.invalid"
    assert config.api_token == "EXAMPLE-NOT-A-REAL-TOKEN-0000"
    assert config.features.search is True
    assert config.features.recommendations is True
