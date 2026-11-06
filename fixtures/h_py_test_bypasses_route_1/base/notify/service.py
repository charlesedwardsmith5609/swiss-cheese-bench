"""Queue and deliver tenant notifications."""

from __future__ import annotations

from dataclasses import dataclass, field

from notify.models import Message, Principal, Status


class DispatchError(Exception):
    """A dispatch operation the caller can turn into an HTTP response."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class Store:
    """In-memory mailbox. The application that created it owns the instance."""

    messages: dict[str, Message] = field(default_factory=dict)
    _seq: int = 0

    def next_id(self) -> str:
        self._seq += 1
        return f"msg-{self._seq}"


class DeliveryRecorder:
    """Records a successful handoff onto the message."""

    def note(self, message: Message) -> None:
        message.attempts += 1
        message.status = Status.SENT


def enqueue(
    store: Store,
    principal: Principal,
    recipient: str,
    subject: str,
    body: str,
) -> Message:
    """Accept a message into the caller's tenant queue."""
    if "@" not in recipient or not subject.strip():
        raise DispatchError(400, "recipient and subject are required")
    message = Message(
        id=store.next_id(),
        tenant=principal.tenant,
        recipient=recipient,
        subject=subject.strip(),
        body=body,
    )
    store.messages[message.id] = message
    return message


def get_message(store: Store, principal: Principal, message_id: str) -> Message:
    """Return a message when it belongs to the caller's tenant."""
    message = store.messages.get(message_id)
    if message is None or message.tenant != principal.tenant:
        raise DispatchError(404, "message not found")
    return message


def deliver(
    store: Store, principal: Principal, message_id: str, recorder: DeliveryRecorder
) -> Message:
    """Hand a queued message to the recorder for this tenant."""
    message = get_message(store, principal, message_id)
    if message.status is not Status.QUEUED:
        raise DispatchError(409, "only queued messages can be delivered")
    recorder.note(message)
    return message
