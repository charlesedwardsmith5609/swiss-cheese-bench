package pricing

import (
	"errors"
)

// ErrUnknownSKU is returned when the catalog has no row for the SKU.
var ErrUnknownSKU = errors.New("pricing: unknown sku")
