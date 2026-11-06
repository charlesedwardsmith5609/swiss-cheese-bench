from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from .models import Session


class SessionStore(Protocol):
    def save(self, session: Session) -> None:
        ...

    def get(self, session_id: str) -> Session | None:
        ...

    def revoke(self, session_id: str, when: datetime) -> bool:
        ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def revoke(self, session_id: str, when: datetime) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.revoked_at is not None:
            return False
        self._sessions[session_id] = replace(session, revoked_at=when)
        return True
