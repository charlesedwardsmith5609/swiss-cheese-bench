package pricing

// SKU identifies a stocked product.
type SKU string

// Item is one catalog row.
type Item struct {
	SKU       SKU
	ListPrice int64
}

// PriceBook holds list prices keyed by SKU.
type PriceBook struct {
	bySKU map[SKU]Item
}

// NewPriceBook copies items into a lookup table. Later items replace earlier ones.
func NewPriceBook(items []Item) *PriceBook {
	bySKU := make(map[SKU]Item, len(items))
	for _, item := range items {
		bySKU[item.SKU] = item
	}
	return &PriceBook{bySKU: bySKU}
}

// Find returns the catalog row for sku.
func (b *PriceBook) Find(sku SKU) (Item, bool) {
	item, ok := b.bySKU[sku]
	return item, ok
}
