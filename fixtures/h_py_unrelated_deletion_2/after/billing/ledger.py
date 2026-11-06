"""Invoice ledger.

issue and void hold the ledger lock for the whole call. The ledger owns the
number book, the statement directory, and both indexes. Invoices are stored
under account_id. Callers share a ledger only by using those methods.
"""

from __future__ import annotations

import threading
from pathlib import Path

from billing.audit import AuditLog
from billing.models import Draft, Invoice
from billing.statements import StatementWriter


class Spool:
    """One statement file. The ledger closes it when writing finishes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._handle = open(path, "w", encoding="utf-8")
        self._closed = False

    def write(self, text: str) -> None:
        self._handle.write(text)

    def close(self) -> None:
        if not self._closed:
            self._handle.close()
            self._closed = True


class NumberBook:
    """Monotonic invoice numbers, with give_back for a post that failed."""

    def __init__(self, start: int = 1000) -> None:
        self._next = start
        self._returned: list[int] = []

    def take(self) -> str:
        if self._returned:
            value = self._returned.pop()
        else:
            value = self._next
            self._next += 1
        return f"INV-{value}"

    def give_back(self, number: str) -> None:
        value = int(number.removeprefix("INV-"))
        self._returned.append(value)


class Ledger:
    """Posts drafts and voids invoices.

    issue and void take the lock. Indexes are updated only while it is held.
    posted_by is stored on the invoice and copied onto the statement.
    """

    def __init__(self, directory: str, audit: AuditLog | None = None) -> None:
        self._directory = directory
        self._audit = audit if audit is not None else AuditLog()
        self._writer = StatementWriter()
        self._numbers = NumberBook()
        self._lock = threading.Lock()
        self._by_number: dict[str, Invoice] = {}
        self._by_account: dict[str, list[str]] = {}
        Path(directory).mkdir(parents=True, exist_ok=True)

    def issue(self, draft: Draft, posted_by: str, now: int) -> Invoice:
        """Post draft under account_id, record the clerk, and write the statement."""
        self._lock.acquire()
        try:
            return self._issue_locked(draft, posted_by, now)
        finally:
            self._lock.release()

    def _issue_locked(self, draft: Draft, posted_by: str, now: int) -> Invoice:
        number = self._numbers.take()
        try:
            invoice = self._compose(draft, number, posted_by, now)
            self._write_statement(invoice)
            self._remember(invoice)
            return invoice
        except Exception:
            self._numbers.give_back(number)
            raise

    def _compose(
        self, draft: Draft, number: str, posted_by: str, now: int
    ) -> Invoice:
        return Invoice(
            number=number,
            account_id=draft.account_id,
            currency=draft.currency,
            lines=tuple(draft.lines),
            memo=draft.memo,
            subtotal_cents=draft.subtotal_cents(),
            tax_cents=draft.tax_cents(),
            issued_at=now,
            posted_by=posted_by,
        )

    def _write_statement(self, invoice: Invoice) -> None:
        spool = Spool(str(Path(self._directory) / f"{invoice.number}.stmt"))
        try:
            spool.write(self._writer.render(invoice))
        finally:
            spool.close()

    def _remember(self, invoice: Invoice) -> None:
        self._by_number[invoice.number] = invoice
        bucket = self._by_account.setdefault(invoice.account_id, [])
        bucket.append(invoice.number)

    def void(self, number: str) -> Invoice:
        """Remove a posted invoice from the account index."""
        self._lock.acquire()
        try:
            invoice = self._by_number.pop(number)
            bucket = self._by_account.get(invoice.account_id, [])
            self._by_account[invoice.account_id] = [
                item for item in bucket if item != number
            ]
            self._audit.record_void(number, invoice.account_id, invoice.total_cents())
            return invoice
        finally:
            self._lock.release()

    def get(self, number: str) -> Invoice:
        return self._by_number[number]

    def numbers_for(self, account_id: str) -> tuple[str, ...]:
        return tuple(self._by_account.get(account_id, ()))

    def statement_text(self, number: str) -> str:
        path = Path(self._directory) / f"{number}.stmt"
        return path.read_text(encoding="utf-8")
