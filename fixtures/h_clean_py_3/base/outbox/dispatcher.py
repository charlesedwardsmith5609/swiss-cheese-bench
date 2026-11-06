"""Immediate delivery of notification messages."""

from __future__ import annotations

import time
from typing import Protocol

from outbox.metrics import Counter
from outbox.models import Message, render_subject
from outbox.policy import Policy, default_policy


class Transport(Protocol):
    """Sink that accepts one rendered message."""

    def deliver(self, message: Message, subject: str) -> None:
        """Hand one message to the mail channel."""


class Dispatcher:
    """Send every accepted message immediately."""

    def __init__(
        self,
        transport: Transport,
        policy: Policy | None = None,
        metrics: Counter | None = None,
    ) -> None:
        self._transport = transport
        self._policy = policy if policy is not None else default_policy()
        self._metrics = metrics if metrics is not None else Counter()
        self.idle_at = 0.0

    def submit(self, actor: str, message: Message) -> str:
        self._policy.authorize(actor, message)
        self._note_idle()
        self._deliver(message)
        return "sent"

    def _note_idle(self) -> None:
        self.idle_at = time.monotonic()

    def _deliver(self, message: Message) -> None:
        subject = message.subject
        subject = render_subject(message)
        self._transport.deliver(message, subject)
        self._metrics.increment("delivered")

    @property
    def metrics(self) -> Counter:
        return self._metrics
