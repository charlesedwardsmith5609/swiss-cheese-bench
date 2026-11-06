package server

import (
	"encoding/json"
	"errors"
	"net/http"
)

type Order struct {
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
}

func createOrder(store *[]Order, o Order) error {
	if o.Quantity <= 0 {
		return errors.New("quantity must be > 0")
	}
	*store = append(*store, o)
	return nil
}

func NewRouter() http.Handler {
	var store []Order
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) })
	mux.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		var o Order
		if err := json.NewDecoder(r.Body).Decode(&o); err != nil {
			http.Error(w, "bad json", http.StatusBadRequest)
			return
		}
		if err := createOrder(&store, o); err != nil {
			http.Error(w, err.Error(), http.StatusUnprocessableEntity)
			return
		}
		w.WriteHeader(http.StatusCreated)
	})
	return mux
}
