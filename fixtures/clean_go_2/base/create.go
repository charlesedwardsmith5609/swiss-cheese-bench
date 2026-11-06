package server

import (
	"encoding/json"
	"net/http"
)

func Create(w http.ResponseWriter, r *http.Request) {
	var v map[string]any
	if err := json.NewDecoder(r.Body).Decode(&v); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusCreated)
}
