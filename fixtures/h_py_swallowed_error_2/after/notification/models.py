from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class Priority(str, Enum):
    """Delivery priority understood by notification transports."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class Notification:
    """A single email notification requested by an application."""

    recipient: str
    subject: str
    body: str
    priority: Priority = Priority.NORMAL
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.recipient.strip():
            raise ValueError("recipient must not be empty")
        if not self.subject.strip():
            raise ValueError("subject must not be empty")


@dataclass(frozen=True)
class DeliveryReceipt:
    """Provider acknowledgement for a submitted notification."""

    provider_id: str
    recipient: str
    priority: Priority
