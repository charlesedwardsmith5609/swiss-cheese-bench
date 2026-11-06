package webhook

import (
	"bytes"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"testing"
)

const testToken = "EXAMPLE-NOT-A-REAL-TOKEN-0000"

func TestHandlerAcceptsAuthenticatedJSON(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken)
	req := httptest.NewRequest(http.MethodPost, "/webhooks", bytes.NewBufferString(`{"action":"opened"}`))
	req.Header.Set("Authorization", "Bearer "+testToken)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
}

func TestHandlerRejectsWrongToken(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken)
	req := httptest.NewRequest(http.MethodPost, "/webhooks", bytes.NewBufferString(`{}`))
	req.Header.Set("Authorization", "Bearer wrong-token")
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusUnauthorized)
	}
}

func TestHandlerRejectsInvalidJSON(t *testing.T) {
	handler := NewHandler(log.New(io.Discard, "", 0), testToken)
	req := httptest.NewRequest(http.MethodPost, "/webhooks", bytes.NewBufferString(`{"action":`))
	req.Header.Set("Authorization", "Bearer "+testToken)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadRequest)
	}
}
