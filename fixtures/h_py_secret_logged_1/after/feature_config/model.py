from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    """Immutable feature-flag values keyed by their public names."""

    values: Mapping[str, bool] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def enabled(self, name: str) -> bool:
        """Return whether a named feature is enabled."""
        return self.values.get(name, False)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Resolved settings used by the application at runtime."""

    endpoint: str
    api_token: str
    features: FeatureFlags
