"""Job records for the in-memory queue."""

from dataclasses import dataclass


@dataclass
class Job:
    """One unit of work waiting on the queue."""

    id: str
    payload: dict[str, object]
    attempts: int = 0
    lease_until: float = 0.0
