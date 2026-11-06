from notification.models import DeliveryReceipt, Notification
from notification.transport import MailTransport


class Dispatcher:
    def __init__(self, transport: MailTransport) -> None:
        self._transport = transport

    def send(self, notification: Notification) -> DeliveryReceipt:
        message_id = self._transport.submit(
            notification.recipient,
            notification.subject,
            notification.body,
        )
        return DeliveryReceipt(
            message_id=message_id,
            recipient=notification.recipient,
        )
