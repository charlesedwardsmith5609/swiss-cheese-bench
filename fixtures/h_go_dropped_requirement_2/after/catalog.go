package pricing

// SKU identifies a stocked product.
type SKU string

// Item is one catalog row. ListCents is the unit list price in cents.
type Item struct {
	SKU       SKU
	ListCents int64
}

// Catalog holds list prices keyed by SKU.
type Catalog struct {
	bySKU map[SKU]Item
}

// NewCatalog copies items into a lookup table. Later items replace earlier
// ones for the same SKU.
func NewCatalog(items []Item) *Catalog {
	bySKU := make(map[SKU]Item, len(items))
	for _, item := range items {
		bySKU[item.SKU] = item
	}
	return &Catalog{bySKU: bySKU}
}

// Lookup returns the catalog row for sku.
func (c *Catalog) Lookup(sku SKU) (Item, bool) {
	item, ok := c.bySKU[sku]
	return item, ok
}
