package pricing

import "testing"

func fixture() (*Service, *Catalog, *Inventory) {
	cat := NewCatalog([]Item{
		{SKU: "BOLT-M8", ListCents: 2505},
		{SKU: "PLATE-A", ListCents: 1250},
		{SKU: "GEAR-12", ListCents: 1001},
		{SKU: "WASHER", ListCents: 400},
		{SKU: "CRATE", ListCents: 2200},
	})
	inv := NewInventory([]Stock{
		{SKU: "BOLT-M8", OnHand: 20, Reserved: 2},
		{SKU: "PLATE-A", OnHand: 10, Reserved: 4},
		{SKU: "GEAR-12", OnHand: 8, Reserved: 0},
		{SKU: "WASHER", OnHand: 40, Reserved: 0},
	})
	return New(cat, inv), cat, inv
}

func TestQuoteRejects(t *testing.T) {
	svc, _, _ := fixture()
	cases := []struct {
		name string
		sku  SKU
		qty  int64
		tier Tier
		want error
	}{
		{"nonpositive", "BOLT-M8", 0, TierStandard, ErrInvalidQuantity},
		{"negative", "BOLT-M8", -2, TierGold, ErrInvalidQuantity},
		{"unknown sku", "NO-SUCH", 1, TierStandard, ErrUnknownSKU},
		{"unknown tier", "BOLT-M8", 1, "platinum", ErrUnknownTier},
		{"over reserved", "PLATE-A", 7, TierStandard, ErrInsufficientStock},
		{"no stock row", "CRATE", 1, TierSilver, ErrInsufficientStock},
	}
	for _, tc := range cases {
		if _, err := svc.Quote(tc.sku, tc.qty, tc.tier); err != tc.want {
			t.Fatalf("%s: got %v, want %v", tc.name, err, tc.want)
		}
	}
	if got := svc.Records(); len(got) != 0 {
		t.Fatalf("errors were audited: %+v", got)
	}
}

func TestQuotePricesAndAudits(t *testing.T) {
	svc, cat, inv := fixture()
	beforeItem, _ := cat.Lookup("BOLT-M8")
	beforeStock, _ := inv.Lookup("PLATE-A")
	cases := []struct {
		sku    SKU
		qty    int64
		tier   Tier
		list   int64
		billed int64
	}{
		{"WASHER", 2, TierStandard, 800, 800},
		{"PLATE-A", 6, TierStandard, 7500, 7500},
		{"PLATE-A", 4, TierGold, 5000, 4500},
		{"GEAR-12", 5, TierGold, 5005, 4505},
		{"BOLT-M8", 2, TierSilver, 5010, 4760},
	}
	for _, tc := range cases {
		line, err := svc.Quote(tc.sku, tc.qty, tc.tier)
		if err != nil || line.ListCents != tc.list || line.BilledCents != tc.billed || line.SKU != tc.sku || line.Qty != tc.qty || line.Tier != tc.tier {
			t.Fatalf("%s: line %+v err %v", tc.sku, line, err)
		}
	}
	got := svc.Records()
	if len(got) != len(cases) {
		t.Fatalf("audit len %d", len(got))
	}
	for i, row := range got {
		tc := cases[i]
		if row.SKU != tc.sku || row.Qty != tc.qty || row.Tier != tc.tier || row.BilledCents != tc.billed {
			t.Fatalf("audit %d: %+v", i, row)
		}
	}
	if item, _ := cat.Lookup("BOLT-M8"); item != beforeItem {
		t.Fatal("catalog price changed")
	}
	if stock, _ := inv.Lookup("PLATE-A"); stock != beforeStock {
		t.Fatal("inventory counts changed")
	}
}
