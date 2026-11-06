"""Queue non-urgent notifications and deliver them through a transport."""

from __future__ import annotations

from typing import Protocol

from outbox.metrics import Counter
from outbox.models import Message, require_message, render_subject
from outbox.policy import Policy, default_policy


class Transport(Protocol):
    """Sink that accepts one rendered message."""

    def deliver(self, message: Message, subject: str) -> None:
        """Hand one message to the mail channel."""


class Dispatcher:
    """Hold non-urgent mail until flush or until the batch is full."""

    def __init__(
        self,
        transport: Transport,
        policy: Policy | None = None,
        metrics: Counter | None = None,
        *,
        digest_limit: int = 0,
        suppressed: frozenset[str] | None = None,
    ) -> None:
        self._transport = transport
        self._policy = policy if policy is not None else default_policy()
        self._metrics = metrics if metrics is not None else Counter()
        self._limit = resolve_digest_limit(digest_limit)
        self._suppressed = {address.strip().lower() for address in (suppressed or ())}
        self._pending: list[Message] = []

    def suppress(self, address: str) -> None:
        self._suppressed.add(address.strip().lower())

    def submit(self, actor: str, message: Message) -> str:
        require_message(message)
        self._policy.authorize(actor, message)
        if self._is_suppressed(message):
            self._metrics.increment("suppressed")
            return "suppressed"
        if message.urgent:
            self._deliver(message)
            return "sent"
        self._pending.append(message)
        if len(self._pending) >= self._limit:
            self.flush()
            return "flushed"
        return "queued"

    def flush(self) -> int:
        """Deliver queued mail. A transport error leaves the failed message queued."""
        sent = 0
        while self._pending:
            message = self._pending[0]
            if self._is_suppressed(message):
                self._pending.pop(0)
                self._metrics.increment("suppressed")
                continue
            self._deliver(message)
            self._pending.pop(0)
            sent += 1
        return sent

    def _is_suppressed(self, message: Message) -> bool:
        return message.recipient.address.strip().lower() in self._suppressed

    def _deliver(self, message: Message) -> None:
        subject = render_subject(message)
        try:
            self._transport.deliver(message, subject)
        except Exception:
            self._metrics.increment("delivery_failed")
            raise
        self._metrics.increment("delivered")

    @property
    def metrics(self) -> Counter:
        return self._metrics

    @property
    def pending(self) -> tuple[Message, ...]:
        return tuple(self._pending)


def resolve_digest_limit(digest_limit: int = 0) -> int:
    """Batch size must be at least 1. Zero means the caller omitted it."""
    if isinstance(digest_limit, bool) or not isinstance(digest_limit, int):
        raise TypeError("digest_limit must be an int")
    if digest_limit < 1:
        raise ValueError("digest_limit must be at least 1")
    return digest_limit
