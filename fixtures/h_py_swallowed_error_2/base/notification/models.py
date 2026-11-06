from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    recipient: str
    subject: str
    body: str


@dataclass(frozen=True)
class DeliveryReceipt:
    message_id: str
    recipient: str
