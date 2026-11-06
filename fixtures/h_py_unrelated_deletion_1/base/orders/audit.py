'''Append-only desk audit. The service is the only writer.'''

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    '''A single desk action. actor is who the desk was told performed it.'''

    action: str
    order_id: str
    actor: str


class AuditLog:
    '''In-memory audit trail. Callers append; readers only filter.'''

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, order_id: str, actor: str) -> AuditEntry:
        '''Append an action. Submit and cancel pass the customer id as actor.'''
        entry = AuditEntry(action=action, order_id=order_id, actor=actor)
        self._entries.append(entry)
        return entry

    def for_order(self, order_id: str) -> list[AuditEntry]:
        '''Entries for one order, oldest first.'''
        return [entry for entry in self._entries if entry.order_id == order_id]
