'''Desk audit trail for issued invoices and applied payments.'''

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    '''One ledger action. actor is the account the desk attributed it to.'''

    action: str
    invoice_id: str
    actor: str


class AuditLog:
    '''Append-only log. The ledger records; readers only filter.'''

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, invoice_id: str, actor: str) -> AuditEntry:
        '''Append an action. Issue and void pass the customer account as actor.'''
        entry = AuditEntry(action=action, invoice_id=invoice_id, actor=actor)
        self._entries.append(entry)
        return entry

    def for_invoice(self, invoice_id: str) -> list[AuditEntry]:
        '''Entries for one invoice, oldest first.'''
        return [entry for entry in self._entries if entry.invoice_id == invoice_id]
