'''Post invoices and apply payments for one billing desk.

Statement text is built here so a clerk can print a copy from the same
object that posted the invoice. Number allocation and balance updates hold
the desk lock for the duration of the mutation.
'''

from __future__ import annotations

from threading import Lock

from billing.models import (
    BillingError,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    Series,
    describe_line,
    format_cents,
    line_total,
    payment_label,
)
from billing.audit import AuditLog


class Ledger:
    '''In-memory invoice book for a single desk.

    The ledger owns the invoice map, the idempotency keys, and the series
    counters. The audit log is supplied by the caller and is not locked here.
    '''

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit
        self._invoices: dict[str, Invoice] = {}
        self._keys: set[str] = set()
        self._series: dict[str, Series] = {}
        self._lock = Lock()

    def add_series(self, series: Series) -> None:
        '''Register a numbering series. The code must be unique on this desk.'''
        if series.code in self._series:
            raise BillingError(f'series {series.code} already registered')
        if series.next_no > series.ceiling:
            raise BillingError(f'series {series.code} starts past its ceiling')
        self._series[series.code] = series

    def issue(
        self,
        account_id: str,
        lines: list[InvoiceLine],
        series_code: str,
    ) -> Invoice:
        '''Assign the next number in the series and store the open invoice.'''
        self._check_lines(lines)
        self._lock.acquire()
        try:
            series = self._require_series(series_code)
            closed = series.next_no > series.ceiling or not series.accepting
            if closed:
                raise BillingError(f'series {series.code} is closed')
            number = series.next_no
            series.next_no += 1
            total = line_total(lines)
            invoice = Invoice(
                invoice_id=f'{series.prefix}-{number:06d}',
                account_id=account_id,
                lines=list(lines),
                balance_cents=total,
            )
            self._invoices[invoice.invoice_id] = invoice
            self._audit.record('issue', invoice.invoice_id, account_id)
            return invoice
        finally:
            self._lock.release()

    def apply_payment(self, invoice_id: str, payment: Payment) -> Invoice:
        '''Apply a captured payment to an open invoice.'''
        if payment.key in self._keys or payment.amt <= 0:
            raise BillingError('payment rejected')
        self._lock.acquire()
        try:
            invoice = self._require_open(invoice_id)
            if payment.account_id != invoice.account_id:
                raise BillingError('payment account does not match the invoice')
            if payment.amt > invoice.balance_cents:
                raise BillingError('payment exceeds the open balance')
            invoice.balance_cents -= payment.amt
            invoice.payments.append(payment)
            if invoice.balance_cents == 0:
                invoice.status = InvoiceStatus.PAID
            self._keys.add(payment.key)
            self._audit.record('apply', invoice.invoice_id, invoice.account_id)
            return invoice
        finally:
            self._lock.release()

    def void(self, invoice_id: str) -> Invoice:
        '''Void an open invoice. Applied payments stay on the document.'''
        self._lock.acquire()
        try:
            invoice = self._require_open(invoice_id)
            invoice.status = InvoiceStatus.VOID
            self._audit.record('void', invoice.invoice_id, invoice.account_id)
            return invoice
        finally:
            self._lock.release()

    def statement(self, invoice_id: str) -> str:
        '''Plain-text statement a clerk can put in a collections letter.'''
        invoice = self._require(invoice_id)
        rows: list[str] = [
            f'Invoice {invoice.invoice_id}',
            f'Account {invoice.account_id}',
            f'Status {invoice.status.value}',
            'Charges',
        ]
        for line in invoice.lines:
            rows.append(describe_line(line))
        rows.append(f'Balance {format_cents(invoice.balance_cents)}')
        if invoice.payments:
            rows.append('Payments')
            for payment in invoice.payments:
                rows.append(payment_label(payment))
        else:
            rows.append('Payments none')
        if invoice.note:
            rows.append(f'Note {invoice.note}')
        rows.append(f'Due {format_cents(invoice.balance_cents)}')
        return '\n'.join(rows) + '\n'

    def get(self, invoice_id: str) -> Invoice:
        '''Return one stored invoice. Missing ids raise BillingError.'''
        return self._require(invoice_id)

    def _check_lines(self, lines: list[InvoiceLine]) -> None:
        if not lines:
            raise BillingError('an invoice needs at least one line')
        for line in lines:
            if line.amt <= 0:
                raise BillingError(f'{line.sku} amt must be positive')

    def _require_series(self, code: str) -> Series:
        try:
            return self._series[code]
        except KeyError as exc:
            raise BillingError(f'unknown series {code}') from exc

    def _require(self, invoice_id: str) -> Invoice:
        try:
            return self._invoices[invoice_id]
        except KeyError as exc:
            raise BillingError(f'unknown invoice {invoice_id}') from exc

    def _require_open(self, invoice_id: str) -> Invoice:
        invoice = self._require(invoice_id)
        if invoice.status is not InvoiceStatus.OPEN:
            raise BillingError(f'invoice {invoice_id} is {invoice.status.value}')
        return invoice
