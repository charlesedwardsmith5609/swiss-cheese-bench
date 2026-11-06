package billing

import (
	"errors"
	"fmt"
	"strings"
	"unicode"
)

var (
	// ErrRequired is returned when a mandatory draft field is blank.
	ErrRequired = errors.New("billing: required field missing")

	// ErrCurrency is returned when currency is outside the supported set.
	ErrCurrency = errors.New("billing: unsupported currency")

	// ErrLine is returned when a charge line cannot be billed.
	ErrLine = errors.New("billing: invalid line")

	// ErrState is returned when a number series cannot issue.
	ErrState = errors.New("billing: bad series")
)

// Line is a single charge.
type Line struct {
	SKU         string
	Description string
	Qty         int64
	UnitCents   Money
}

// Draft is an invoice that has not yet been issued.
type Draft struct {
	ID         string
	CustomerID string
	Currency   string
	Lines      []Line
}

var currencies = map[string]struct{}{
	"USD": {},
	"EUR": {},
	"GBP": {},
}

func normalizeToken(raw, field string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" || len(raw) > 64 {
		return "", fmt.Errorf("%w: %s", ErrRequired, field)
	}
	for _, r := range raw {
		if unicode.IsSpace(r) || r > unicode.MaxASCII {
			return "", fmt.Errorf("%w: %s", ErrRequired, field)
		}
	}
	return raw, nil
}

func normalizeCurrency(code string) (string, error) {
	code = strings.ToUpper(strings.TrimSpace(code))
	if code == "" {
		return "", fmt.Errorf("%w: currency", ErrRequired)
	}
	if _, ok := currencies[code]; !ok {
		return "", fmt.Errorf("%w: %s", ErrCurrency, code)
	}
	return code, nil
}

func normalizeLines(rows []linePayload) ([]Line, error) {
	if len(rows) == 0 {
		return nil, fmt.Errorf("%w: lines", ErrRequired)
	}
	out := make([]Line, 0, len(rows))
	for _, row := range rows {
		sku, err := normalizeToken(row.SKU, "sku")
		if err != nil {
			return nil, err
		}
		if row.Qty <= 0 {
			return nil, fmt.Errorf("%w: qty", ErrLine)
		}
		out = append(out, Line{
			SKU:         sku,
			Description: strings.TrimSpace(row.Description),
			Qty:         row.Qty,
			UnitCents:   Money(row.UnitCents),
		})
	}
	return out, nil
}
