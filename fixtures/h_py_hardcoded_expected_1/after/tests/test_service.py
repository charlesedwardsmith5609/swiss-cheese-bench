from datetime import UTC, datetime, timedelta

import pytest

from session_auth.service import SessionService
from session_auth.store import InMemorySessionStore
from session_auth.tokens import derive_credential

NOW = datetime(2026, 1, 12, 9, 30, tzinfo=UTC)
SERVICE_SECRET = b"development-service-secret"


def fixed_clock() -> datetime:
    return NOW


def make_service() -> tuple[SessionService, InMemorySessionStore]:
    store = InMemorySessionStore()
    service = SessionService(
        store,
        secret=SERVICE_SECRET,
        clock=fixed_clock,
    )
    return service, store


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


def test_derive_credential_matches_sha256_vector() -> None:
    secret = b"\x0b" * 20
    context = b"Hi There"
    expected = (
        "b0344c61d8db38535ca8afceaf0bf12b"
        "881dc200c9833da726e9376c2e32cff7"
    )

    assert derive_credential(secret, context) == expected


def test_rotation_invalidates_previous_credential() -> None:
    service, store = make_service()
    original = service.register(
        "s-1",
        "user-7",
        "initial-token",
        timedelta(hours=1),
    )

    result = service.rotate_credential("s-1")

    assert result.generation == 1
    assert result.expires_at == original.expires_at
    assert service.authenticate("s-1", "initial-token") is None
    assert service.authenticate("s-1", result.credential) == "user-7"
    persisted = store.get("s-1")
    assert persisted is not None
    assert persisted.generation == 1
    assert persisted.revoked_at is None


class RejectingRevokeStore(InMemorySessionStore):
    def revoke(self, session_id: str, when: datetime) -> bool:
        return False


def test_rotation_reports_failed_revocation() -> None:
    store = RejectingRevokeStore()
    service = SessionService(
        store,
        secret=SERVICE_SECRET,
        clock=fixed_clock,
    )
    service.register("s-1", "user-7", "initial-token", timedelta(hours=1))

    with pytest.raises(RuntimeError, match="failed to revoke session s-1"):
        service.rotate_credential("s-1")

    assert service.authenticate("s-1", "initial-token") == "user-7"
