from dataclasses import dataclass
from typing import Mapping, Protocol

from notification.models import Priority


@dataclass(frozen=True)
class EmailPayload:
    """Transport-ready representation of an email notification."""

    recipient: str
    subject: str
    body: str
    priority: Priority
    metadata: Mapping[str, str]


class MailTransport(Protocol):
    def submit(self, payload: EmailPayload) -> str:
        """Submit a payload and return the provider's identifier."""
        ...


class InMemoryTransport:
    """Small deterministic transport used by tests and local callers."""

    def __init__(self) -> None:
        self.sent: list[EmailPayload] = []

    def submit(self, payload: EmailPayload) -> str:
        self.sent.append(payload)
        return f"mail-{len(self.sent)}"
