"""Authorization statements for outbound notifications."""

from __future__ import annotations

from dataclasses import dataclass

from outbox.models import Message


@dataclass(frozen=True)
class Statement:
    """One allow or deny rule. ``*`` matches any substring."""

    effect: str
    principals: tuple[str, ...]
    actions: tuple[str, ...]
    resources: tuple[str, ...]


def _matches(pattern: str, value: str) -> bool:
    parts = pattern.split("*")
    if len(parts) == 1:
        return pattern == value
    if not value.startswith(parts[0]) or (parts[-1] and not value.endswith(parts[-1])):
        return False
    index = 0
    for part in parts:
        if not part:
            continue
        found = value.find(part, index)
        if found < 0:
            return False
        index = found + len(part)
    return True


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
        resource = f"mailbox:{message.recipient.address.strip().lower()}"
        action = "notify:send"
        for statement in self._statements:
            if statement.effect == "Deny" and _covers(statement, actor, action, resource):
                raise PermissionError(actor)
        for statement in self._statements:
            if statement.effect == "Allow" and _covers(statement, actor, action, resource):
                return
        raise PermissionError(actor)


def default_policy() -> Policy:
    """Deny bounce addresses for every principal, then allow the mailer role."""
    return Policy(
        (
            Statement(
                effect="Deny",
                principals=("*",),
                actions=("notify:send",),
                resources=("mailbox:bounce+*@*",),
            ),
            Statement(
                effect="Allow",
                principals=("role:mailer",),
                actions=("notify:send",),
                resources=("mailbox:*",),
            ),
        )
    )
