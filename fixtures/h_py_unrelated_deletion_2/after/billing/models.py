'''Invoice documents accepted by the billing desk.

Monetary amounts are integer cents so statement columns match the payments
table. A numbering series carries the next number to issue and the last
number that series may legally assign.
'''

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InvoiceStatus(Enum):
    '''Lifecycle of an invoice stored on the ledger.'''

    OPEN = 'open'
    PAID = 'paid'
    VOID = 'void'


class BillingError(Exception):
    '''The desk rejected an invoice or payment operation.'''


@dataclass
class Series:
    '''A block of invoice numbers owned by one desk.

    next_no is the next number to assign. ceiling is the highest number that
    may still be assigned. accepting is false after the desk closes the series.
    '''

    code: str
    prefix: str
    next_no: int
    ceiling: int
    accepting: bool = True


@dataclass(frozen=True)
class InvoiceLine:
    '''One charge row on an invoice.

    amount_cents is the extended amount in cents, already multiplied by quantity.
    description is the customer-facing label printed on the statement.
    '''

    sku: str
    description: str
    amount_cents: int


@dataclass(frozen=True)
class Payment:
    '''Money captured against a customer account.

    key is the client idempotency key. amount_cents is the captured amount in cents.
    method is the tender, such as card or wire.
    '''

    key: str
    account_id: str
    amount_cents: int
    method: str = 'card'


@dataclass
class Invoice:
    '''A numbered invoice stored on the ledger.

    balance_cents starts at the line total and falls as payments apply.
    '''

    invoice_id: str
    account_id: str
    lines: list[InvoiceLine]
    status: InvoiceStatus = InvoiceStatus.OPEN
    balance_cents: int = 0
    payments: list[Payment] = field(default_factory=list)
    note: str = ''


def format_cents(cents: int) -> str:
    '''Render an integer cent amount as a dollar string.'''
    sign = '-' if cents < 0 else ''
    whole, frac = divmod(abs(cents), 100)
    return f'{sign}{whole}.{frac:02d}'


def line_total(lines: list[InvoiceLine]) -> int:
    '''Sum of charge rows, in cents.'''
    return sum(line.amount_cents for line in lines)


def describe_line(line: InvoiceLine) -> str:
    '''Single charge label used on the statement.'''
    return f'{line.sku} {line.description} {line.amount_cents}'


def payment_label(payment: Payment) -> str:
    '''Single payment label used on the statement.'''
    return f'{payment.method} {format_cents(payment.amount_cents)} ref {payment.key}'
