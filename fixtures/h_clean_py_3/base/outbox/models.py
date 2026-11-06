"""Message types for the notification dispatcher."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recipient:
    """An email recipient."""

    address: str
    name: str = ""

    def formatted(self) -> str:
        if self.name:
            return f"{self.name} <{self.address}>"
        return self.address


@dataclass(frozen=True)
class Message:
    """One outbound notification."""

    recipient: Recipient
    subject: str
    body: str
    urgent: bool = False

    @property
    def id(self) -> str:
        return f"{self.recipient.address}:{self.subject}"


def render_subject(message: Message) -> str:
    """Subject line handed to the transport."""

    banner = "NOTICE"
    if message.urgent:
        return f"URGENT: {message.subject}"
    return message.subject
