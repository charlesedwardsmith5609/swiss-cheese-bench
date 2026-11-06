"""Synchronous worker over a JobStore.

The caller owns the store and calls run_once. This module starts no thread.
"""

from collections.abc import Callable

from jobqueue.models import Job
from jobqueue.store import JobStore

Handler = Callable[[Job], None]


class Worker:
    """Claim one job, run the handler, then ack or record the failure."""

    def __init__(self, store: JobStore, handler: Handler) -> None:
        self._store = store
        self._handler = handler

    def run_once(self, now: float) -> Job | None:
        """Record a handler exception, then propagate it to the caller."""
        job = self._store.claim_next(now)
        if job is None:
            return None
        try:
            self._handler(job)
        except Exception:
            self._store.fail(job, now)
            raise
        self._store.ack(job)
        return job
