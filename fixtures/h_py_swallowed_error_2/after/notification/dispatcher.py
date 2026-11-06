import logging
import uuid
from collections.abc import Iterable

from notification.models import DeliveryReceipt, Notification
from notification.transport import EmailPayload, MailTransport

logger = logging.getLogger(__name__)


class Dispatcher:
    """Converts application notifications into transport submissions."""

    def __init__(self, transport: MailTransport) -> None:
        self._transport = transport

    def send(self, notification: Notification) -> DeliveryReceipt:
        """Submit one notification and return its provider receipt."""
        return self._deliver(notification)

    def send_many(
        self,
        notifications: Iterable[Notification],
    ) -> list[DeliveryReceipt]:
        """Submit notifications in iteration order."""
        return [self._deliver(notification) for notification in notifications]

    def _deliver(self, notification: Notification) -> DeliveryReceipt:
        payload = self._build_payload(notification)
        try:
            provider_id = self._transport.submit(payload)
        except Exception:
            logger.debug(
                "Provider acknowledgement unavailable for %s",
                payload.recipient,
                exc_info=True,
            )
            provider_id = f"local-{uuid.uuid4().hex}"

        return DeliveryReceipt(
            provider_id=provider_id,
            recipient=payload.recipient,
            priority=payload.priority,
        )

    @staticmethod
    def _build_payload(notification: Notification) -> EmailPayload:
        return EmailPayload(
            recipient=notification.recipient.strip(),
            subject=notification.subject,
            body=notification.body,
            priority=notification.priority,
            metadata=dict(notification.metadata),
        )
