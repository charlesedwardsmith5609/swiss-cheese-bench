package webhook

import (
	"crypto/subtle"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"time"
)

type Handler struct {
	logger       *log.Logger
	sharedToken  string
	maxBodyBytes int64
	now          func() time.Time
}

func NewHandler(logger *log.Logger, sharedToken string, maxBodyBytes int64) *Handler {
	return &Handler{
		logger:       logger,
		sharedToken:  sharedToken,
		maxBodyBytes: maxBodyBytes,
		now:          time.Now,
	}
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

	deliveryID := r.Header.Get("X-Delivery-ID")
	event := r.Header.Get("X-Webhook-Event")
	if deliveryID == "" || event == "" {
		http.Error(w, "delivery ID and event are required", http.StatusBadRequest)
		return
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, h.maxBodyBytes+1))
	if err != nil {
		http.Error(w, "could not read request", http.StatusBadRequest)
		return
	}
	if int64(len(body)) > h.maxBodyBytes {
		http.Error(w, "request too large", http.StatusRequestEntityTooLarge)
		return
	}
	if !json.Valid(body) {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	receivedAt := h.now().UTC()
	summary := summarizeDelivery(r, len(body), receivedAt)
	h.logger.Printf("webhook accepted: %+v", summary)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(receipt{
		Status:     "accepted",
		DeliveryID: deliveryID,
		Event:      event,
		ReceivedAt: receivedAt,
	})
}

func (h *Handler) authorized(value string) bool {
	expected := "Bearer " + h.sharedToken
	return subtle.ConstantTimeCompare([]byte(value), []byte(expected)) == 1
}
