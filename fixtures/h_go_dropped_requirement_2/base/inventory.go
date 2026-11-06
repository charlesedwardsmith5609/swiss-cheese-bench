package pricing

// Stock is the warehouse position for one SKU.
type Stock struct {
	SKU      SKU
	OnHand   int64
	Reserved int64
}

// Inventory is a snapshot of on-hand and reserved units.
type Inventory struct {
	bySKU map[SKU]Stock
}

// NewInventory copies rows into a lookup table. Later rows replace earlier ones.
func NewInventory(rows []Stock) *Inventory {
	bySKU := make(map[SKU]Stock, len(rows))
	for _, row := range rows {
		bySKU[row.SKU] = row
	}
	return &Inventory{bySKU: bySKU}
}

// Find returns the stock row for sku.
func (inv *Inventory) Find(sku SKU) (Stock, bool) {
	row, ok := inv.bySKU[sku]
	return row, ok
}
