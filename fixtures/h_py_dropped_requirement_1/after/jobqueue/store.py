"""In-memory store of runnable, dead-lettered, and completed jobs.

The caller thread owns a JobStore. Nothing here starts a thread.
"""

from jobqueue.models import (
    DEFAULT_BASE_DELAY,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    Completion,
    Job,
)


class JobStore:
    """Leases, backoff, and dead-letter state for one queue."""

    def __init__(
        self,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_delay: float = DEFAULT_BASE_DELAY,
    ) -> None:
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self.dead: list[Job] = []
        self.completed: list[Completion] = []

    def enqueue(self, job_id: str, body: dict[str, object], not_before: float = 0.0) -> Job:
        if job_id in self._jobs:
            raise ValueError(f"duplicate job id {job_id}")
        job = Job(id=job_id, body=body, not_before=not_before)
        self._jobs[job_id] = job
        self._order.append(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def runnable_ids(self) -> list[str]:
        return list(self._order)

    def claim_next(self, now: float) -> Job | None:
        for job_id in self._order:
            job = self._jobs[job_id]
            if not self._eligible(job, now):
                continue
            job.state = "leased"
            job.lease_until = now + self.lease_seconds
            return job
        return None

    def ack(self, job: Job) -> Completion:
        job.state = "done"
        job.lease_until = 0.0
        self._order.remove(job.id)
        record = Completion(job_id=job.id, attempts=job.attempts)
        self.completed.append(record)
        return record

    def fail(self, job: Job, now: float) -> None:
        job.attempts += 1
        job.lease_until = 0.0
        if job.attempts >= self.max_attempts:
            job.state = "dead"
            self._order.remove(job.id)
            self.dead.append(job)
            return
        job.state = "pending"
        job.available_at = now + self.base_delay * (2 ** (job.attempts - 1))

    def _eligible(self, job: Job, now: float) -> bool:
        """True once the lease is free and backoff has elapsed."""
        return job.lease_until <= now and job.available_at <= now
