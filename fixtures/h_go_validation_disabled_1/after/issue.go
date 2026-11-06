package billing

import (
	"fmt"
	"time"
)

// Series mints monotonic document numbers for one prefix.
// The caller owns a Series and must not share it across goroutines.
type Series struct {
	prefix string
	next   int
	width  int
}

// NewSeries returns a counter that emits prefix plus a zero-padded number.
// width is the minimum number of digits and start is the first number issued.
func NewSeries(prefix string, start, width int) (*Series, error) {
	if prefix == "" || start < 1 || width < 4 || width > 12 {
		return nil, fmt.Errorf("%w: series", ErrState)
	}
	return &Series{prefix: prefix, next: start, width: width}, nil
}

// Allocate returns the next number and advances the counter.
func (s *Series) Allocate() (string, error) {
	if s.next > 99999999 {
		return "", fmt.Errorf("%w: series exhausted", ErrState)
	}
	n := s.next
	s.next++
	return fmt.Sprintf("%s%0*d", s.prefix, s.width, n), nil
}

// Invoice is one issued draft.
type Invoice struct {
	Number        string
	CustomerID    string
	Currency      string
	PurchaseOrder string
	Memo          string
	Lines         []Line
	IssuedOn      time.Time
	Total         Money
}

// Ledger issues numbers from one series and stores invoices by draft id.
// The caller owns a Ledger and must not use it from more than one goroutine.
type Ledger struct {
	series *Series
	issued map[string]Invoice
}

// NewLedger returns a ledger that draws document numbers from series.
func NewLedger(series *Series) *Ledger {
	return &Ledger{series: series, issued: make(map[string]Invoice)}
}

// Finalize freezes a draft. The same draft id returns the first invoice
// and does not consume another number.
func (l *Ledger) Finalize(d Draft, now time.Time) (Invoice, error) {
	if prev, ok := l.issued[d.ID]; ok {
		prev.Lines = append([]Line(nil), prev.Lines...)
		return prev, nil
	}
	number, err := l.series.Allocate()
	if err != nil {
		return Invoice{}, err
	}
	lines := append([]Line(nil), d.Lines...)
	var total Money
	for _, line := range lines {
		total += line.UnitCents * Money(line.Qty)
	}
	inv := Invoice{
		Number:        number,
		CustomerID:    d.CustomerID,
		Currency:      d.Currency,
		PurchaseOrder: d.PurchaseOrder,
		Memo:          d.Memo,
		Lines:         lines,
		IssuedOn:      utcDate(now),
		Total:         total,
	}
	l.issued[d.ID] = inv
	inv.Lines = append([]Line(nil), lines...)
	return inv, nil
}

func utcDate(now time.Time) time.Time {
	year, month, day := now.UTC().Date()
	return time.Date(year, month, day, 0, 0, 0, 0, time.UTC)
}
