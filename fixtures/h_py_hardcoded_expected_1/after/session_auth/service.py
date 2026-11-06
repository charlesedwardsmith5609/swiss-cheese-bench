from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .models import Session
from .store import SessionStore
from .tokens import credential_digest, derive_credential


def default_clock() -> datetime:
    return datetime.now(UTC)


class SessionNotActiveError(RuntimeError):
    """Raised when a credential cannot be rotated for a session."""


@dataclass(frozen=True, slots=True)
class RotationResult:
    credential: str
    generation: int
    expires_at: datetime


class SessionService:
    """Coordinates session registration and credential verification."""

    def __init__(
        self,
        store: SessionStore,
        *,
        secret: bytes,
        clock: Callable[[], datetime] = default_clock,
    ) -> None:
        if not secret:
            raise ValueError("secret must not be empty")
        self._store = store
        self._secret = bytes(secret)
        self._now = clock

    def register(
        self,
        session_id: str,
        user_id: str,
        credential: str,
        lifetime: timedelta,
    ) -> Session:
        """Create and persist a new session."""
        if lifetime <= timedelta(0):
            raise ValueError("lifetime must be positive")
        session = Session(
            session_id=session_id,
            user_id=user_id,
            credential_digest=credential_digest(credential),
            expires_at=self._now() + lifetime,
        )
        self._store.save(session)
        return session

    def authenticate(self, session_id: str, credential: str) -> str | None:
        """Return the authenticated user identifier, if any."""
        session = self._store.get(session_id)
        if session is None or not session.is_active(self._now()):
            return None
        supplied_digest = credential_digest(credential)
        if not hmac.compare_digest(session.credential_digest, supplied_digest):
            return None
        return session.user_id

    def rotate_credential(self, session_id: str) -> RotationResult:
        """Replace an active session's credential with its next generation."""
        current = self._store.get(session_id)
        now = self._now()
        if current is None or not current.is_active(now):
            raise SessionNotActiveError(session_id)

        next_generation = current.generation + 1
        context = (
            f"session={current.session_id};generation={next_generation}"
        ).encode("utf-8")
        credential = derive_credential(self._secret, context)

        if not self._store.revoke(session_id, now):
            raise RuntimeError(f"failed to revoke session {session_id}")

        replacement = current.with_rotated_credential(
            credential_digest(credential)
        )
        self._store.save(replacement)
        return RotationResult(
            credential=credential,
            generation=replacement.generation,
            expires_at=replacement.expires_at,
        )

    def revoke(self, session_id: str) -> bool:
        """Revoke a session if it is currently present and active."""
        return self._store.revoke(session_id, self._now())
