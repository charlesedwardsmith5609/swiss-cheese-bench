from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Session:
    """Persisted authentication state for one user session."""

    session_id: str
    user_id: str
    credential_digest: bytes
    expires_at: datetime
    generation: int = 0
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """Return whether the session can currently authenticate."""
        return self.revoked_at is None and now < self.expires_at

    def with_rotated_credential(self, digest: bytes) -> Session:
        """Create the next active generation of this session."""
        return replace(
            self,
            credential_digest=digest,
            generation=self.generation + 1,
            revoked_at=None,
        )
