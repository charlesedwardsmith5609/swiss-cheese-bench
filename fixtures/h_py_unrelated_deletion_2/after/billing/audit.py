'''Desk audit trail for issued invoices and applied payments.'''

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    '''One ledger action. posted_by is the clerk the desk attributed it to.'''

    action: str
    invoice_id: str
    posted_by: str


class AuditLog:
    '''Append-only log owned by the caller.

    The ledger appends one entry for issue, apply, and void. Readers filter
    by invoice id and do not take the ledger lock.
    '''

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, invoice_id: str, posted_by: str) -> AuditEntry:
        '''Append an action attributed to the posting clerk.'''
        entry = AuditEntry(action=action, invoice_id=invoice_id, posted_by=posted_by)
        self._entries.append(entry)
        return entry

    def for_invoice(self, invoice_id: str) -> list[AuditEntry]:
        '''Entries for one invoice, oldest first.'''
        return [entry for entry in self._entries if entry.invoice_id == invoice_id]
