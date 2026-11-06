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

	// ErrField is returned when a supplied value breaks a length or shape rule.
	ErrField = errors.New("billing: invalid field")

	// ErrState is returned when a number series cannot issue.
	ErrState = errors.New("billing: bad series")
)

// Line is a single charge.
type Line struct {
	SKU         string
	Description string
	Qty         int64
	UnitCents   Money
	CostCenter  string
}

// Draft is an invoice that has not yet been issued.
type Draft struct {
	ID            string
	CustomerID    string
	Currency      string
	PurchaseOrder string
	Memo          string
	Lines         []Line
}

const defaultCurrency = "USD"

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
	var err error
	code, err = fill(strings.ToUpper(code), defaultCurrency, "currency", true)
	if err != nil {
		return "", err
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
		center, err := normalizeCostCenter(row.CostCenter)
		if err != nil {
			return nil, err
		}
		out = append(out, Line{
			SKU:         sku,
			Description: strings.TrimSpace(row.Description),
			Qty:         row.Qty,
			UnitCents:   Money(row.UnitCents),
			CostCenter:  center,
		})
	}
	return out, nil
}

func fill(value, fallback, field string, required bool) (string, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		value = strings.TrimSpace(fallback)
	}
	if required && value == "" {
		return "", fmt.Errorf("%w: %s", ErrRequired, field)
	}
	return value, nil
}

func normalizeBound(raw, field string, max int) (string, error) {
	text, err := fill(raw, "", field, false)
	if err != nil {
		return "", err
	}
	if len([]rune(text)) > max {
		return "", fmt.Errorf("%w: %s", ErrField, field)
	}
	return text, nil
}

func normalizeCostCenter(raw string) (string, error) {
	text, err := fill(raw, "", "cost_center", false)
	if err != nil {
		return "", err
	}
	if text == "" {
		return "", nil
	}
	if len(text) > 16 {
		return "", fmt.Errorf("%w: cost_center", ErrField)
	}
	for i := 0; i < len(text); i++ {
		c := text[i]
		if (c < 'a' || c > 'z') && (c < 'A' || c > 'Z') && (c < '0' || c > '9') {
			return "", fmt.Errorf("%w: cost_center", ErrField)
		}
	}
	return text, nil
}
