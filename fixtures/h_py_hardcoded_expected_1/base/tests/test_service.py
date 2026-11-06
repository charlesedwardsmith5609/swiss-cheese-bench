from datetime import UTC, datetime, timedelta

from session_auth.service import SessionService
from session_auth.store import InMemorySessionStore

NOW = datetime(2026, 1, 12, 9, 30, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


def make_service() -> tuple[SessionService, InMemorySessionStore]:
    store = InMemorySessionStore()
    return SessionService(store, clock=fixed_clock), store


def test_registered_credential_authenticates() -> None:
    service, _ = make_service()
    service.register("s-1", "user-7", "initial-token", timedelta(hours=1))

    assert service.authenticate("s-1", "initial-token") == "user-7"
    assert service.authenticate("s-1", "wrong-token") is None


def test_unknown_session_is_rejected() -> None:
    service, _ = make_service()

    assert service.authenticate("missing", "initial-token") is None


def test_revoked_session_is_rejected() -> None:
    service, _ = make_service()
    service.register("s-1", "user-7", "initial-token", timedelta(hours=1))

    assert service.revoke("s-1") is True
    assert service.authenticate("s-1", "initial-token") is None
