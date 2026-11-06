package billing

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
)

// ParseDraft decodes one JSON invoice draft.
// Object keys that this package does not know are rejected.
func ParseDraft(buf []byte) (Draft, error) {
	dec := json.NewDecoder(bytes.NewReader(buf))
	dec.DisallowUnknownFields()
	var raw draftPayload
	if err := dec.Decode(&raw); err != nil {
		return Draft{}, err
	}
	var extra struct{}
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return Draft{}, errors.New("billing: trailing JSON")
		}
		return Draft{}, err
	}
	return raw.toDraft()
}

type draftPayload struct {
	ID         string        `json:"id"`
	CustomerID string        `json:"customer_id"`
	Currency   string        `json:"currency"`
	Lines      []linePayload `json:"lines"`
}

type linePayload struct {
	SKU         string `json:"sku"`
	Description string `json:"description"`
	Qty         int64  `json:"qty"`
	UnitCents   int64  `json:"unit_cents"`
}

func (p draftPayload) toDraft() (Draft, error) {
	id, err := normalizeToken(p.ID, "id")
	if err != nil {
		return Draft{}, err
	}
	customer, err := normalizeToken(p.CustomerID, "customer_id")
	if err != nil {
		return Draft{}, err
	}
	currency, err := normalizeCurrency(p.Currency)
	if err != nil {
		return Draft{}, err
	}
	lines, err := normalizeLines(p.Lines)
	if err != nil {
		return Draft{}, err
	}
	return Draft{
		ID:         id,
		CustomerID: customer,
		Currency:   currency,
		Lines:      lines,
	}, nil
}
