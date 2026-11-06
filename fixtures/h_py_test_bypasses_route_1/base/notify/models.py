"""Message records owned by a tenant mailbox."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class Principal:
    """Caller resolved from a bearer token."""

    user_id: str
    tenant: str
    token: str


@dataclass
class Message:
    """One outbound notification accepted into the queue."""

    id: str
    tenant: str
    recipient: str
    subject: str
    body: str
    status: Status = Status.QUEUED
    attempts: int = 0
