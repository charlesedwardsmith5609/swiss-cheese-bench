from notification.dispatcher import Dispatcher
from notification.models import Notification
from notification.transport import InMemoryTransport


def test_send_submits_notification() -> None:
    transport = InMemoryTransport()
    dispatcher = Dispatcher(transport)

    receipt = dispatcher.send(
        Notification(
            recipient="reader@example.com",
            subject="Weekly update",
            body="The report is ready.",
        )
    )

    assert receipt.message_id == "mail-1"
    assert receipt.recipient == "reader@example.com"
    assert transport.sent == [
        ("reader@example.com", "Weekly update", "The report is ready.")
    ]
