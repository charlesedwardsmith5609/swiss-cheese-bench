"""Message records and caller roles for the dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Role(Enum):
    """What a caller is allowed to do inside a tenant."""

    MEMBER = "member"
    OPERATOR = "operator"


@dataclass(frozen=True)
class Principal:
    """Caller resolved from a bearer token."""

    user_id: str
    tenant: str
    role: Role
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
