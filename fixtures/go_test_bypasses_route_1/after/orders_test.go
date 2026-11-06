package server

import "testing"

func TestCreateOrderRejectsZeroQuantity(t *testing.T) {
	var store []Order
	if err := createOrder(&store, Order{SKU: "a", Quantity: 0}); err == nil {
		t.Fatal("expected error")
	}
}
