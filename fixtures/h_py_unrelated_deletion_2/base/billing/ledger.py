"""Invoice ledger.

issue and void hold the ledger lock for the whole call. The ledger owns the
number book, the statement directory, and both indexes. Callers share a
ledger only by using those methods; they do not touch the indexes directly.
"""

from __future__ import annotations

import threading
from pathlib import Path

from billing.models import Draft, Invoice
from billing.statements import StatementWriter
from billing.audit import AuditLog


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

    The lock taken by issue and void is the only guard around the indexes.
    """

    def __init__(self, directory: str, audit: AuditLog | None = None) -> None:
        self._directory = directory
        self._audit = audit if audit is not None else AuditLog()
        self._writer = StatementWriter()
        self._numbers = NumberBook()
        self._lock = threading.Lock()
        self._by_number: dict[str, Invoice] = {}
        self._by_customer: dict[str, list[str]] = {}
        Path(directory).mkdir(parents=True, exist_ok=True)

    def issue(self, draft: Draft, now: int) -> Invoice:
        """Post draft, index it by customer_id, and write the statement file."""
        self._lock.acquire()
        try:
            number = self._numbers.take()
            spool = Spool(str(Path(self._directory) / f"{number}.stmt"))
            try:
                invoice = Invoice(
                    number=number,
                    customer_id=draft.customer_id,
                    currency=draft.currency,
                    lines=tuple(draft.lines),
                    memo=draft.memo,
                    subtotal_cents=draft.subtotal_cents(),
                    issued_at=now,
                )
                spool.write(self._writer.render(invoice))
                self._by_number[number] = invoice
                self._by_customer.setdefault(draft.customer_id, []).append(number)
                self._audit.record_post(number, draft.customer_id, invoice.total_cents())
                return invoice
            except Exception:
                self._numbers.give_back(number)
                raise
            finally:
                spool.close()
        finally:
            self._lock.release()

    def void(self, number: str) -> Invoice:
        """Remove a posted invoice from the customer index."""
        self._lock.acquire()
        try:
            invoice = self._by_number.pop(number)
            bucket = self._by_customer.get(invoice.customer_id, [])
            self._by_customer[invoice.customer_id] = [
                item for item in bucket if item != number
            ]
            self._audit.record_void(number, invoice.customer_id, invoice.total_cents())
            return invoice
        finally:
            self._lock.release()

    def get(self, number: str) -> Invoice:
        return self._by_number[number]

    def numbers_for(self, customer_id: str) -> tuple[str, ...]:
        return tuple(self._by_customer.get(customer_id, ()))

    def statement_text(self, number: str) -> str:
        path = Path(self._directory) / f"{number}.stmt"
        return path.read_text(encoding="utf-8")
