package billing

import (
	"errors"
	"strings"
	"testing"
	"time"
)

func TestParseDraft(t *testing.T) {
	d, err := ParseDraft([]byte(`{"id":"d1","customer_id":"c1","currency":"usd","lines":[{"sku":"A-1","description":" bolt ","qty":3,"unit_cents":250}]}`))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if d.ID != "d1" || d.CustomerID != "c1" || d.Currency != "USD" || len(d.Lines) != 1 {
		t.Fatalf("draft: %+v", d)
	}
	if d.Lines[0].Description != "bolt" || d.Lines[0].Qty != 3 || d.Lines[0].UnitCents != 250 {
		t.Fatalf("line: %+v", d.Lines[0])
	}
	if Format(d.Lines[0].UnitCents) != "2.50" {
		t.Fatalf("format: %s", Format(d.Lines[0].UnitCents))
	}
}

func TestParseDraftRejects(t *testing.T) {
	reject := func(raw string, target error) {
		t.Helper()
		_, err := ParseDraft([]byte(raw))
		if target == nil {
			if err == nil {
				t.Fatalf("expected an error for %s", raw)
			}
			return
		}
		if !errors.Is(err, target) {
			t.Fatalf("got %v want %v", err, target)
		}
	}
	reject(`{"id":"d","customer_id":"c","currency":"USD","lines":[],"region":"us"}`, nil)
	reject(`{"id":"d","customer_id":"","currency":"USD","lines":[{"sku":"a","qty":1,"unit_cents":1}]}`, ErrRequired)
	reject(`{"id":"d","customer_id":"c","currency":"XYZ","lines":[{"sku":"a","qty":1,"unit_cents":1}]}`, ErrCurrency)
	reject(`{"id":"d","customer_id":"c","currency":"USD","lines":[]}`, ErrRequired)
	reject(`{"id":"d","customer_id":"c","currency":"USD","lines":[{"sku":"a","qty":0,"unit_cents":1}]}`, ErrLine)
}

func TestSeriesWidth(t *testing.T) {
	s, err := NewSeries("INV-", 1001, 4)
	if err != nil {
		t.Fatalf("series: %v", err)
	}
	got, err := s.Allocate()
	if err != nil || got != "INV-1001" {
		t.Fatalf("got %s %v", got, err)
	}
	if _, err := NewSeries("INV-", 1, 3); err == nil {
		t.Fatal("width 3 accepted")
	}
}

func TestOptionalFieldsAndFinalize(t *testing.T) {
	raw := `{"id":"d-9","customer_id":"acme","currency":"eur","purchase_order":" po-77 ","memo":" net 30 ","lines":[{"sku":"sku1","description":" widget ","qty":2,"unit_cents":1500,"cost_center":"CC12"}]}`
	d, err := ParseDraft([]byte(raw))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if d.Currency != "EUR" || d.PurchaseOrder != "po-77" || d.Memo != "net 30" {
		t.Fatalf("header: %+v", d)
	}
	if d.Lines[0].Description != "widget" || d.Lines[0].CostCenter != "CC12" {
		t.Fatalf("line: %+v", d.Lines[0])
	}
	series, err := NewSeries("INV-", 7, 4)
	if err != nil {
		t.Fatalf("series: %v", err)
	}
	ledger := NewLedger(series)
	now := time.Date(2026, 3, 8, 18, 4, 0, 0, time.FixedZone("EDT", -4*3600))
	first, err := ledger.Finalize(d, now)
	if err != nil {
		t.Fatalf("finalize: %v", err)
	}
	second, err := ledger.Finalize(d, now.Add(48*time.Hour))
	if err != nil {
		t.Fatalf("again: %v", err)
	}
	wantDate := time.Date(2026, 3, 8, 0, 0, 0, 0, time.UTC)
	if first.Number != "INV-0007" || first.Total != 3000 || !first.IssuedOn.Equal(wantDate) {
		t.Fatalf("issued: %+v", first)
	}
	if first.PurchaseOrder != "po-77" || first.Memo != "net 30" || first.Lines[0].CostCenter != "CC12" {
		t.Fatalf("copied: %+v", first)
	}
	if second.Number != first.Number || second.Total != first.Total || !second.IssuedOn.Equal(first.IssuedOn) {
		t.Fatalf("idempotent: %+v", second)
	}
	next, err := series.Allocate()
	if err != nil || next != "INV-0008" {
		t.Fatalf("next: %s %v", next, err)
	}
	longPO := `{"id":"d","customer_id":"c","currency":"USD","purchase_order":"` + strings.Repeat("p", 33) + `","lines":[{"sku":"a","qty":1,"unit_cents":1}]}`
	if _, err := ParseDraft([]byte(longPO)); !errors.Is(err, ErrField) {
		t.Fatalf("po: %v", err)
	}
	longMemo := `{"id":"d","customer_id":"c","currency":"USD","memo":"` + strings.Repeat("m", 281) + `","lines":[{"sku":"a","qty":1,"unit_cents":1}]}`
	if _, err := ParseDraft([]byte(longMemo)); !errors.Is(err, ErrField) {
		t.Fatalf("memo: %v", err)
	}
	badCenter := `{"id":"d","customer_id":"c","currency":"USD","lines":[{"sku":"a","qty":1,"unit_cents":1,"cost_center":"no good"}]}`
	if _, err := ParseDraft([]byte(badCenter)); !errors.Is(err, ErrField) {
		t.Fatalf("center: %v", err)
	}
	blank, err := ParseDraft([]byte(`{"id":"d","customer_id":"c","currency":"USD","purchase_order":" ","memo":" ","lines":[{"sku":"a","qty":1,"unit_cents":1,"cost_center":" "}]}`))
	if err != nil || blank.PurchaseOrder != "" || blank.Memo != "" || blank.Lines[0].CostCenter != "" {
		t.Fatalf("blank: %+v %v", blank, err)
	}
}
