from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSettings:
    search: bool = False
    recommendations: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    endpoint: str
    api_token: str
    features: FeatureSettings
