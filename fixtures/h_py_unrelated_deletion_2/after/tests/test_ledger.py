"""Posting and void tests. They call Ledger.issue and Ledger.void."""

from __future__ import annotations

from pathlib import Path

import pytest

from billing.ledger import Ledger
from billing.models import Draft, LineItem


def _draft() -> Draft:
    return Draft(
        account_id="acct-1",
        currency="USD",
        lines=[
            LineItem("SKU-1", "Widget", 2, 2500, tax_bps=1000),
            LineItem("SKU-2", "Gasket", 1, 400, tax_bps=0),
        ],
        memo="net 30",
    )


def test_issue_indexes_and_writes_statement(tmp_path: Path) -> None:
    ledger = Ledger(str(tmp_path))
    invoice = ledger.issue(_draft(), posted_by="clerk-9", now=1_700_000_000)
    assert invoice.account_id == "acct-1"
    assert invoice.posted_by == "clerk-9"
    assert invoice.number == "INV-1000"
    assert invoice.subtotal_cents == 5400
    assert invoice.tax_cents == 500
    assert invoice.total_cents() == 5900
    assert ledger.numbers_for("acct-1") == (invoice.number,)
    text = ledger.statement_text(invoice.number)
    assert "account acct-1" in text
    assert "posted_by clerk-9" in text
    assert "SKU-1 Widget x2 net 5000 tax 500" in text
    assert "totals" in text
    assert "subtotal 5400" in text
    assert "tax 500" in text
    assert text.endswith("total 5900\n")


def test_void_drops_index(tmp_path: Path) -> None:
    ledger = Ledger(str(tmp_path))
    invoice = ledger.issue(_draft(), posted_by="clerk-9", now=1_700_000_000)
    voided = ledger.void(invoice.number)
    assert voided.number == invoice.number
    assert voided.account_id == "acct-1"
    assert ledger.numbers_for("acct-1") == ()
    with pytest.raises(KeyError):
        ledger.get(invoice.number)
