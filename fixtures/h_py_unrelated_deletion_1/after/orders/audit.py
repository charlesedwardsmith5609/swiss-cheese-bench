'''Append-only desk audit. The service is the only writer.'''

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    '''A single desk action. requested_by is the actor string the desk was given.'''

    action: str
    order_id: str
    requested_by: str


class AuditLog:
    '''In-memory audit trail. Callers append; readers only filter.'''

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, order_id: str, requested_by: str) -> AuditEntry:
        '''Append an action attributed to requested_by.'''
        entry = AuditEntry(action=action, order_id=order_id, requested_by=requested_by)
        self._entries.append(entry)
        return entry

    def for_order(self, order_id: str) -> list[AuditEntry]:
        '''Entries for one order, oldest first.'''
        return [entry for entry in self._entries if entry.order_id == order_id]
