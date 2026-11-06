"""Tests for the pending-job store."""

from jobqueue.store import JobStore


def test_enqueue_appends_in_order() -> None:
    store = JobStore()
    store.enqueue("a", {"n": 1})
    store.enqueue("b", {"n": 2})
    assert store.pending_ids() == ["a", "b"]
    found = store.get("a")
    assert found is not None
    assert found.payload == {"n": 1}


def test_get_unknown_is_none() -> None:
    store = JobStore()
    assert store.get("missing") is None
