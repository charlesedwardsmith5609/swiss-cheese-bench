class PricingMetrics:
    """In-process counters for pricing request outcomes."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def increment(self, name: str) -> None:
        self._counts[name] = self._counts.get(name, 0) + 1

    def value(self, name: str) -> int:
        return self._counts.get(name, 0)
