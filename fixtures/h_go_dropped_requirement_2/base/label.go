package pricing

import (
	"strconv"
	"strings"
)

// Label formats a SKU and an on-hand count for a picker sheet.
func Label(sku SKU, onHand int64) string {
	var b strings.Builder
	b.WriteString(string(sku))
	b.WriteByte(' ')
	b.WriteString(strconv.FormatInt(onHand, 10))
	return b.String()
}
