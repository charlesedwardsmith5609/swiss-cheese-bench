"""Tests for leasing, backoff, dead-letter, and the worker."""

import pytest

from jobqueue.models import Job
from jobqueue.store import JobStore
from jobqueue.worker import Worker


def test_enqueue_appends_in_order() -> None:
    store = JobStore()
    store.enqueue("a", {"n": 1})
    store.enqueue("b", {"n": 2})
    assert store.runnable_ids() == ["a", "b"]
    found = store.get("a")
    assert found is not None and found.body == {"n": 1}


def test_get_unknown_is_none() -> None:
    store = JobStore()
    assert store.get("missing") is None


def test_claim_when_not_before_has_arrived() -> None:
    store = JobStore()
    store.enqueue("j", {"n": 1}, not_before=50.0)
    claimed = store.claim_next(50.0)
    assert claimed is not None and claimed.not_before == 50.0


def test_lease_blocks_until_expiry() -> None:
    store = JobStore(lease_seconds=10)
    store.enqueue("j", {"n": 1})
    assert store.claim_next(100.0) is not None
    assert store.claim_next(109.0) is None
    again = store.claim_next(110.0)
    assert again is not None and again.attempts == 0


def test_backoff_doubles_each_failure() -> None:
    store = JobStore(base_delay=2)
    store.enqueue("j", {"n": 1})
    job = store.claim_next(0.0)
    assert job is not None
    store.fail(job, 0.0)
    assert job.attempts == 1 and job.available_at == 2.0
    assert store.claim_next(1.9) is None
    retried = store.claim_next(2.0)
    assert retried is not None
    store.fail(retried, 2.0)
    assert retried.attempts == 2 and retried.available_at == 6.0


def test_fifth_failure_is_dead_lettered() -> None:
    store = JobStore(base_delay=2, max_attempts=5)
    store.enqueue("j", {"n": 1})
    now = 0.0
    last: Job | None = None
    for _ in range(5):
        last = store.claim_next(now)
        assert last is not None
        store.fail(last, now)
        now = last.available_at
    assert last is not None and last.state == "dead"
    assert [item.id for item in store.dead] == ["j"]
    assert store.claim_next(now + 1000.0) is None


def test_worker_retries_then_acks() -> None:
    store = JobStore(base_delay=2)
    store.enqueue("j", {"n": 2})
    seen: list[dict[str, object]] = []
    calls = 0

    def handler(job: Job) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        seen.append(job.body)

    worker = Worker(store, handler)
    with pytest.raises(RuntimeError, match="boom"):
        worker.run_once(0.0)
    assert store.claim_next(1.0) is None
    assert worker.run_once(2.0) is not None
    assert seen == [{"n": 2}]
    assert store.completed[0].attempts == 1
    assert store.runnable_ids() == []
