package pricing

import (
	"errors"
)

// ErrUnknownSKU is returned when the catalog has no row for the SKU.
var ErrUnknownSKU = errors.New("pricing: unknown sku")

// ErrUnknownTier is returned when the tier is not standard, silver, or gold.
var ErrUnknownTier = errors.New("pricing: unknown tier")

// ErrInvalidQuantity is returned when the requested quantity is not positive.
var ErrInvalidQuantity = errors.New("pricing: quantity must be positive")

// ErrInsufficientStock is returned when the requested quantity exceeds available units.
var ErrInsufficientStock = errors.New("pricing: insufficient stock")
