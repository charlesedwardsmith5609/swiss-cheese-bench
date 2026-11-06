package pricing

// Stock is the warehouse position for one SKU.
type Stock struct {
	SKU      SKU
	OnHand   int64
	Reserved int64
}

// Available is the number of units that can still be quoted.
func (s Stock) Available() int64 {
	return s.OnHand - s.Reserved
}

// Inventory is a snapshot of on-hand and reserved units.
type Inventory struct {
	bySKU map[SKU]Stock
}

// NewInventory copies rows into a lookup table. Later rows replace earlier
// ones for the same SKU.
func NewInventory(rows []Stock) *Inventory {
	bySKU := make(map[SKU]Stock, len(rows))
	for _, row := range rows {
		bySKU[row.SKU] = row
	}
	return &Inventory{bySKU: bySKU}
}

// Lookup returns the stock row for sku.
func (inv *Inventory) Lookup(sku SKU) (Stock, bool) {
	row, ok := inv.bySKU[sku]
	return row, ok
}
