"""Tests for the notification dispatcher."""

from __future__ import annotations

import pytest

from outbox.models import Message, Recipient, render_subject
from outbox.metrics import Counter
from outbox.dispatcher import Dispatcher


ACTOR = "role:mailer"


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def deliver(self, message: Message, subject: str) -> None:
        self.sent.append((message.recipient.formatted(), subject))


def make_dispatcher(transport: RecordingTransport) -> Dispatcher:
    return Dispatcher(transport)


def _message(address: str, subject: str, *, urgent: bool = False) -> Message:
    return Message(Recipient(address), subject, "Please review.", urgent)


def test_urgent_mail_is_delivered() -> None:
    transport = RecordingTransport()
    dispatcher = make_dispatcher(transport)
    message = Message(
        Recipient("ada@shop.example.com", "Ada"),
        "Invoice 1042",
        "Please review.",
        True,
    )
    assert dispatcher.submit(ACTOR, message) == "sent"
    assert transport.sent == [("Ada <ada@shop.example.com>", "URGENT: Invoice 1042")]


def test_unknown_actor_is_rejected() -> None:
    transport = RecordingTransport()
    dispatcher = make_dispatcher(transport)
    stranger = _message("ada@shop.example.com", "Invoice 1042", urgent=True)
    with pytest.raises(PermissionError):
        dispatcher.submit("role:stranger", stranger)
    assert transport.sent == []


def test_render_subject_marks_urgent_only() -> None:
    urgent = _message("ada@shop.example.com", "Invoice 1042", urgent=True)
    quiet = _message("ada@shop.example.com", "Invoice 1042")
    assert render_subject(urgent) == "URGENT: Invoice 1042"
    assert render_subject(quiet) == "Invoice 1042"


def test_counter_reads_zero_until_incremented() -> None:
    counter = Counter()
    assert counter.get("delivered") == 0
    counter.increment("delivered")
    assert counter.get("delivered") == 1
