'''Plain-text statements for collections letters.

Rendering takes an invoice that has already been issued. It does not allocate
a number, apply a payment, or take the desk lock, so a letter can be built
without posting.
'''

from __future__ import annotations

from billing.models import Invoice, describe_line, format_cents, payment_label


def render_statement(invoice: Invoice) -> str:
    '''Render one invoice as text a clerk can drop into a letter.'''
    rows = _heading(invoice)
    rows.extend(_charges(invoice))
    rows.extend(_payments(invoice))
    if invoice.note:
        rows.append(f'Note {invoice.note}')
    rows.append(f'Due {format_cents(invoice.balance_cents)}')
    return '\n'.join(rows) + '\n'


def _heading(invoice: Invoice) -> list[str]:
    '''Identification lines printed above the charges.'''
    return [
        f'Invoice {invoice.invoice_id}',
        f'Account {invoice.account_id}',
        f'Status {invoice.status.value}',
    ]


def _charges(invoice: Invoice) -> list[str]:
    '''Charge section in ledger order, followed by the open balance.'''
    rows = ['Charges']
    rows.extend(describe_line(line) for line in invoice.lines)
    rows.append(f'Balance {format_cents(invoice.balance_cents)}')
    return rows


def _payments(invoice: Invoice) -> list[str]:
    '''Payment section. An invoice with no payments still records that fact.'''
    if not invoice.payments:
        return ['Payments none']
    rows = ['Payments']
    rows.extend(payment_label(payment) for payment in invoice.payments)
    return rows
