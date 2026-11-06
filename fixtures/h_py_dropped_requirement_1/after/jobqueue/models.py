"""Job records for the in-memory queue."""

from dataclasses import dataclass

DEFAULT_LEASE_SECONDS = 30.0
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BASE_DELAY = 2.0


@dataclass
class Job:
    """A unit of work.

    not_before is the unix time before which the job is not yet due.
    available_at is the backoff instant and is tracked on its own.
    """

    id: str
    body: dict[str, object]
    attempts: int = 0
    not_before: float = 0.0
    available_at: float = 0.0
    lease_until: float = 0.0
    state: str = "pending"


@dataclass(frozen=True)
class Completion:
    """Ack record. attempts is the number of recorded failures."""

    job_id: str
    attempts: int
