package server

import (
	"encoding/json"
	"net/http"
	"strconv"
)

var items = make([]string, 500)

func ListItems(w http.ResponseWriter, r *http.Request) {
	page, err := strconv.Atoi(r.URL.Query().Get("page"))
	if err != nil || page < 0 {
		page = 0
	}
	size, err := strconv.Atoi(r.URL.Query().Get("size"))
	if err != nil || size <= 0 {
		size = 20
	}
	start := page * size
	if start > len(items) {
		start = len(items)
	}
	end := start + size
	if end > len(items) {
		end = len(items)
	}
	_ = json.NewEncoder(w).Encode(items[start:end])
}
