from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .models import Session
from .store import SessionStore
from .tokens import credential_digest


def default_clock() -> datetime:
    return datetime.now(UTC)


class SessionService:
    def __init__(
        self,
        store: SessionStore,
        *,
        clock: Callable[[], datetime] = default_clock,
    ) -> None:
        self._store = store
        self._clock = clock

    def register(
        self,
        session_id: str,
        user_id: str,
        credential: str,
        lifetime: timedelta,
    ) -> Session:
        if lifetime <= timedelta(0):
            raise ValueError("lifetime must be positive")
        session = Session(
            session_id=session_id,
            user_id=user_id,
            credential_digest=credential_digest(credential),
            expires_at=self._clock() + lifetime,
        )
        self._store.save(session)
        return session

    def authenticate(self, session_id: str, credential: str) -> str | None:
        session = self._store.get(session_id)
        if session is None or not session.is_active(self._clock()):
            return None
        supplied_digest = credential_digest(credential)
        if not hmac.compare_digest(session.credential_digest, supplied_digest):
            return None
        return session.user_id

    def revoke(self, session_id: str) -> bool:
        return self._store.revoke(session_id, self._clock())
