"""FIFO store for pending jobs.

The caller thread owns a JobStore. Nothing here starts a thread.
"""

from jobqueue.models import Job


class JobStore:
    """Insertion-ordered jobs waiting to be taken."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []

    def enqueue(self, job_id: str, payload: dict[str, object]) -> Job:
        job = Job(id=job_id, payload=payload)
        self._jobs[job_id] = job
        self._order.append(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def pending_ids(self) -> list[str]:
        return list(self._order)
