package billing

import (
	"errors"
	"testing"
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
	got, err := s.Take()
	if err != nil || got != "INV-1001" {
		t.Fatalf("got %s %v", got, err)
	}
	if _, err := NewSeries("INV-", 1, 3); err == nil {
		t.Fatal("width 3 accepted")
	}
}
