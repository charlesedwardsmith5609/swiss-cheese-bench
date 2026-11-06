package server

import (
	"encoding/json"
	"net/http"
)

const maxBody = 1 << 20

func Create(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxBody)
	var v map[string]any
	if err := json.NewDecoder(r.Body).Decode(&v); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusCreated)
}
