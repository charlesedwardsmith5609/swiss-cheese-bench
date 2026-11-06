package webhook

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const testToken = "EXAMPLE-NOT-A-REAL-TOKEN-0000"

func TestHandlerReturnsDeliveryReceipt(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken, defaultMaxBodyBytes)
	receivedAt := time.Date(2026, time.November, 6, 15, 30, 0, 0, time.UTC)
	handler.now = func() time.Time { return receivedAt }

	req := newWebhookRequest(`{"action":"opened"}`)
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
	var got receipt
	if err := json.NewDecoder(recorder.Body).Decode(&got); err != nil {
		t.Fatalf("decode receipt: %v", err)
	}
	if got.Status != "accepted" || got.DeliveryID != "delivery-42" || got.Event != "issue.opened" {
		t.Fatalf("unexpected receipt: %+v", got)
	}
	if !got.ReceivedAt.Equal(receivedAt) {
		t.Fatalf("received_at = %s, want %s", got.ReceivedAt, receivedAt)
	}
}

func TestHandlerRejectsMissingDeliveryMetadata(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken, defaultMaxBodyBytes)
	req := newWebhookRequest(`{}`)
	req.Header.Del("X-Delivery-ID")
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadRequest)
	}
}

func TestHandlerRejectsWrongToken(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken, defaultMaxBodyBytes)
	req := newWebhookRequest(`{}`)
	req.Header.Set("Authorization", "Bearer wrong-token")
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusUnauthorized)
	}
}

func TestHandlerRejectsInvalidJSON(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken, defaultMaxBodyBytes)
	req := newWebhookRequest(`{"action":`)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadRequest)
	}
}

func TestHandlerEnforcesConfiguredBodyLimit(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken, 8)
	req := newWebhookRequest(`{"value":"too long"}`)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusRequestEntityTooLarge)
	}
}

func newWebhookRequest(body string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/webhooks", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+testToken)
	req.Header.Set("X-Delivery-ID", "delivery-42")
	req.Header.Set("X-Webhook-Event", "issue.opened")
	return req
}
