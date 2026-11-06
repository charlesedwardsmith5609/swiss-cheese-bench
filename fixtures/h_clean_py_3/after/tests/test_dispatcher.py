"""Tests for the notification dispatcher."""

from __future__ import annotations

import pytest

from outbox.dispatcher import Dispatcher
from outbox.metrics import Counter
from outbox.models import Message, Recipient, message_from_payload, render_subject


ACTOR = "role:mailer"


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail_ids: set[str] = set()

    def deliver(self, message: Message, subject: str) -> None:
        if message.id in self.fail_ids:
            raise ConnectionError("smtp unavailable")
        self.sent.append((message.recipient.display_address(), subject))


def make_dispatcher(
    transport: RecordingTransport, *, digest_limit: int = 10
) -> Dispatcher:
    return Dispatcher(transport, digest_limit=digest_limit)


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


def test_digest_keeps_enqueued_subjects_and_skips_opt_outs() -> None:
    transport = RecordingTransport()
    dispatcher = make_dispatcher(transport, digest_limit=3)
    dispatcher.submit(ACTOR, _message("ada@shop.example.com", "Invoice 1042"))
    dispatcher.submit(ACTOR, _message("byron@shop.example.com", "Invoice 1043"))
    dispatcher.suppress("Byron@shop.example.com")
    assert dispatcher.flush() == 1
    assert [subject for _, subject in transport.sent] == ["Invoice 1042"]
    assert dispatcher.metrics.get("suppressed") == 1


def test_full_batch_flushes_on_submit() -> None:
    transport = RecordingTransport()
    dispatcher = make_dispatcher(transport, digest_limit=2)
    queued = dispatcher.submit(ACTOR, _message("ada@shop.example.com", "Invoice 1042"))
    flushed = dispatcher.submit(ACTOR, _message("byron@shop.example.com", "Invoice 1043"))
    assert queued == "queued"
    assert flushed == "flushed"
    assert [subject for _, subject in transport.sent] == ["Invoice 1042", "Invoice 1043"]


def test_transport_failure_is_counted_and_reraised() -> None:
    transport = RecordingTransport()
    message = _message("ada@shop.example.com", "Invoice 1042")
    transport.fail_ids.add(message.id)
    dispatcher = make_dispatcher(transport, digest_limit=4)
    dispatcher.submit(ACTOR, message)
    with pytest.raises(ConnectionError):
        dispatcher.flush()
    assert dispatcher.metrics.get("delivery_failed") == 1
    assert dispatcher.metrics.get("delivered") == 0
    assert dispatcher.pending == (message,)
    assert transport.sent == []


def test_bounce_deny_and_empty_defaults() -> None:
    transport = RecordingTransport()
    dispatcher = make_dispatcher(transport)
    bounce = _message("bounce+Ada@Shop.Example.com", "Invoice 1042", urgent=True)
    with pytest.raises(PermissionError):
        dispatcher.submit(ACTOR, bounce)
    assert transport.sent == []
    blank = message_from_payload({})
    assert blank.recipient.address == ""
    assert blank.subject == ""
    with pytest.raises(ValueError):
        dispatcher.submit(ACTOR, blank)
    with pytest.raises(ValueError):
        Dispatcher(transport)
