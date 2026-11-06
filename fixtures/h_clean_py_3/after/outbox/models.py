"""Message types for the notification dispatcher."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recipient:
    """An email recipient."""

    address: str
    name: str = ""

    def display_address(self) -> str:
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

    if message.urgent:
        return f"URGENT: {message.subject}"
    return message.subject


def message_from_payload(payload: dict[str, object]) -> Message:
    """Missing address and subject stay empty until require_message."""
    address = payload.get("address", "")
    name = payload.get("name", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    urgent = payload.get("urgent", False)
    if not isinstance(address, str) or not isinstance(name, str):
        raise TypeError("address and name must be strings")
    if not isinstance(subject, str) or not isinstance(body, str):
        raise TypeError("subject and body must be strings")
    if not isinstance(urgent, bool):
        raise TypeError("urgent must be a bool")
    return Message(Recipient(address, name), subject, body, urgent)


def require_message(message: Message) -> None:
    """Reject a blank or malformed recipient, or a blank subject."""
    address = message.recipient.address
    pieces = address.split("@")
    if len(pieces) != 2 or not pieces[0] or not pieces[1]:
        raise ValueError("recipient or subject is invalid")
    domain = pieces[1]
    if (
        "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or any(ch.isspace() for ch in address)
        or not message.subject.strip()
    ):
        raise ValueError("recipient or subject is invalid")
