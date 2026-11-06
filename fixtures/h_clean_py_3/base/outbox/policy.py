"""Authorization statements for outbound notifications."""

from __future__ import annotations

from dataclasses import dataclass

from outbox.models import Message


@dataclass(frozen=True)
class Statement:
    """One allow or deny rule. A trailing ``*`` matches a prefix."""

    effect: str
    principals: tuple[str, ...]
    actions: tuple[str, ...]
    resources: tuple[str, ...]


def _matches(pattern: str, value: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith("*") and pattern.count("*") == 1:
        return value.startswith(pattern[:-1])
    return pattern == value


def _covers(statement: Statement, actor: str, action: str, resource: str) -> bool:
    if not any(_matches(pattern, actor) for pattern in statement.principals):
        return False
    if not any(_matches(pattern, action) for pattern in statement.actions):
        return False
    return any(_matches(pattern, resource) for pattern in statement.resources)


class Policy:
    """Allow a send only when an Allow statement matches. Otherwise deny."""

    def __init__(self, statements: tuple[Statement, ...]) -> None:
        self._statements = statements

    def authorize(self, actor: str, message: Message) -> None:
        resource = f"mailbox:{message.recipient.address}"
        for statement in self._statements:
            if statement.effect != "Allow":
                continue
            if _covers(statement, actor, "notify:send", resource):
                return
        raise PermissionError(actor)


def default_policy() -> Policy:
    """The mailer role may send to any mailbox."""
    return Policy(
        (
            Statement(
                effect="Allow",
                principals=("role:mailer",),
                actions=("notify:send",),
                resources=("mailbox:*",),
            ),
        )
    )
