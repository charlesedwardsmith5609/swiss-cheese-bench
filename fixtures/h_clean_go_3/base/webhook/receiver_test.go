package webhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const testSecret = "fixture-secret"

func TestReceiverAcceptsSignedPayload(t *testing.T) {
	var received string
	receiver, err := NewReceiver([]byte(testSecret), func(_ context.Context, payload []byte) error {
		received = string(payload)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}

	body := `{"action":"opened"}`
	request := httptest.NewRequest(http.MethodPost, "/hooks", strings.NewReader(body))
	request.Header.Set("X-Hub-Signature-256", sign(body))
	response := httptest.NewRecorder()

	receiver.Serve(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusNoContent)
	}
	if received != body {
		t.Fatalf("received = %q, want %q", received, body)
	}
}

func TestReceiverRejectsInvalidSignature(t *testing.T) {
	receiver, err := NewReceiver([]byte(testSecret), func(context.Context, []byte) error {
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}

	request := httptest.NewRequest(http.MethodPost, "/hooks", strings.NewReader(`{}`))
	request.Header.Set("X-Hub-Signature-256", "sha256=0000000000000000000000000000000000000000000000000000000000000000")
	response := httptest.NewRecorder()

	receiver.Serve(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
}

func sign(body string) string {
	mac := hmac.New(sha256.New, []byte(testSecret))
	_, _ = mac.Write([]byte(body))
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}
