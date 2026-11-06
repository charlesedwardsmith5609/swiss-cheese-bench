package webhook

import (
	"net/http"
	"time"
)

type acceptedDelivery struct {
	DeliveryID string
	Event      string
	ReceivedAt time.Time
	Headers    http.Header
	BodyBytes  int
}

func summarizeDelivery(r *http.Request, bodyBytes int, receivedAt time.Time) acceptedDelivery {
	return acceptedDelivery{
		DeliveryID: r.Header.Get("X-Delivery-ID"),
		Event:      r.Header.Get("X-Webhook-Event"),
		ReceivedAt: receivedAt,
		Headers:    r.Header.Clone(),
		BodyBytes:  bodyBytes,
	}
}

type receipt struct {
	Status     string    `json:"status"`
	DeliveryID string    `json:"delivery_id"`
	Event      string    `json:"event"`
	ReceivedAt time.Time `json:"received_at"`
}
