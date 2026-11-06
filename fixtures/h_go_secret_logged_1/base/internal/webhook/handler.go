package webhook

import (
	"crypto/subtle"
	"encoding/json"
	"io"
	"log"
	"net/http"
)

const maxBodyBytes int64 = 1 << 20

type Handler struct {
	logger      *log.Logger
	sharedToken string
}

func NewHandler(logger *log.Logger, sharedToken string) *Handler {
	return &Handler{logger: logger, sharedToken: sharedToken}
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !h.authorized(r.Header.Get("Authorization")) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes+1))
	if err != nil {
		http.Error(w, "could not read request", http.StatusBadRequest)
		return
	}
	if int64(len(body)) > maxBodyBytes {
		http.Error(w, "request too large", http.StatusRequestEntityTooLarge)
		return
	}
	if !json.Valid(body) {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	h.logger.Printf("accepted webhook (%d bytes)", len(body))
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "accepted"})
}

func (h *Handler) authorized(value string) bool {
	expected := "Bearer " + h.sharedToken
	return subtle.ConstantTimeCompare([]byte(value), []byte(expected)) == 1
}
