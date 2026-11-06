import pytest

from notification.dispatcher import Dispatcher
from notification.models import Notification, Priority
from notification.transport import EmailPayload, InMemoryTransport


def test_send_submits_normalized_payload() -> None:
    transport = InMemoryTransport()
    dispatcher = Dispatcher(transport)

    receipt = dispatcher.send(
        Notification(
            recipient="  reader@example.com ",
            subject="Weekly update",
            body="The report is ready.",
            priority=Priority.HIGH,
            metadata={"campaign": "weekly"},
        )
    )

    assert receipt.provider_id == "mail-1"
    assert receipt.recipient == "reader@example.com"
    assert receipt.priority is Priority.HIGH
    assert transport.sent == [
        EmailPayload(
            recipient="reader@example.com",
            subject="Weekly update",
            body="The report is ready.",
            priority=Priority.HIGH,
            metadata={"campaign": "weekly"},
        )
    ]


def test_send_many_preserves_input_order() -> None:
    transport = InMemoryTransport()
    dispatcher = Dispatcher(transport)
    notifications = [
        Notification(
            recipient="first@example.com",
            subject="First",
            body="One",
            priority=Priority.LOW,
        ),
        Notification(
            recipient="second@example.com",
            subject="Second",
            body="Two",
            priority=Priority.HIGH,
        ),
    ]

    receipts = dispatcher.send_many(notifications)

    assert [receipt.provider_id for receipt in receipts] == ["mail-1", "mail-2"]
    assert [payload.recipient for payload in transport.sent] == [
        "first@example.com",
        "second@example.com",
    ]
    assert [payload.priority for payload in transport.sent] == [
        Priority.LOW,
        Priority.HIGH,
    ]


@pytest.mark.parametrize(
    ("recipient", "subject"),
    [("", "Subject"), ("   ", "Subject"), ("reader@example.com", " ")],
)
def test_notification_rejects_missing_headers(
    recipient: str,
    subject: str,
) -> None:
    with pytest.raises(ValueError):
        Notification(recipient=recipient, subject=subject, body="Body")
