package pricing

import "fmt"

// Label formats a SKU and an on-hand count for a picker sheet.
func Label(sku SKU, onHand int64) string {
	return fmt.Sprintf("%s %d", sku, onHand)
}
