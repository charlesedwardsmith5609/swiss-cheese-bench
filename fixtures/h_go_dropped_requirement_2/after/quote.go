package pricing

// Tier is the customer price tier applied to a quote.
type Tier string

const (
	TierStandard Tier = "standard"
	TierSilver   Tier = "silver"
	TierGold     Tier = "gold"
)

// Line is one priced quote. Amounts are integer cents.
type Line struct {
	SKU         SKU
	Qty         int64
	Tier        Tier
	ListCents   int64
	BilledCents int64
}

// Record is the audit row stored for a successful quote.
type Record struct {
	SKU         SKU
	Qty         int64
	Tier        Tier
	BilledCents int64
}

// Service prices quotes from a catalog and an inventory snapshot.
// The caller owns the catalog, the inventory, and the service.
type Service struct {
	cat     *Catalog
	inv     *Inventory
	records []Record
}

// New returns a service over cat and inv.
func New(cat *Catalog, inv *Inventory) *Service {
	return &Service{cat: cat, inv: inv}
}

// Records returns a copy of the audit log in append order.
func (s *Service) Records() []Record {
	out := make([]Record, len(s.records))
	copy(out, s.records)
	return out
}

func tierNumer(tier Tier) (int64, error) {
	switch tier {
	case TierStandard:
		return 100, nil
	case TierSilver:
		return 95, nil
	case TierGold:
		return 90, nil
	default:
		return 0, ErrUnknownTier
	}
}

// Quote prices one SKU for a tier and quantity.
func (s *Service) Quote(sku SKU, qty int64, tier Tier) (Line, error) {
	if qty <= 0 {
		return Line{}, ErrInvalidQuantity
	}
	item, ok := s.cat.Lookup(sku)
	if !ok {
		return Line{}, ErrUnknownSKU
	}
	numer, err := tierNumer(tier)
	if err != nil {
		return Line{}, err
	}
	var stock Stock
	if row, found := s.inv.Lookup(sku); found {
		stock = row
	}
	if qty > stock.Available() {
		return Line{}, ErrInsufficientStock
	}
	listTotal := item.ListCents * qty
	billed := (listTotal*numer + 50) / 100
	s.records = append(s.records, Record{SKU: sku, Qty: qty, Tier: tier, BilledCents: billed})
	return Line{SKU: sku, Qty: qty, Tier: tier, ListCents: listTotal, BilledCents: billed}, nil
}
