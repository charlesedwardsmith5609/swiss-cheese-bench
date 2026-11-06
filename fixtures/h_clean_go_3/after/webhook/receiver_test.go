package webhook

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const testSecret = "fixture-secret"

func TestReceiverDispatchesPush(t *testing.T) {
	var received PushEvent
	receiver := newTestReceiver(t, func(_ context.Context, event PushEvent) error {
		received = event
		return nil
	})

	body := `{"ref":"refs/heads/main","repository":{"full_name":"acme/widgets"},"commits":[{"id":"4f3c2a1","message":"Ship receiver"}]}`
	request := signedRequest(http.MethodPost, "push", body)
	response := httptest.NewRecorder()

	receiver.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusNoContent)
	}
	if received.Ref != "refs/heads/main" {
		t.Fatalf("ref = %q, want refs/heads/main", received.Ref)
	}
	if received.Repository.FullName != "acme/widgets" {
		t.Fatalf("repository = %q, want acme/widgets", received.Repository.FullName)
	}
	if len(received.Commits) != 1 || received.Commits[0].ID != "4f3c2a1" {
		t.Fatalf("commits = %#v", received.Commits)
	}
}

func TestReceiverRejectsInvalidRequests(t *testing.T) {
	oversized := strings.Repeat("x", int(maxPayloadBytes)+1)
	tests := []struct {
		name      string
		method    string
		event     string
		body      string
		signature string
		want      int
	}{
		{name: "method", method: http.MethodGet, event: "push", body: `{}`, want: http.StatusMethodNotAllowed},
		{name: "missing signature", method: http.MethodPost, event: "push", body: `{}`, want: http.StatusUnauthorized},
		{name: "bad signature", method: http.MethodPost, event: "push", body: `{}`, signature: "sha256=0000000000000000000000000000000000000000000000000000000000000000", want: http.StatusUnauthorized},
		{name: "missing event", method: http.MethodPost, body: `{}`, signature: sign(`{}`), want: http.StatusBadRequest},
		{name: "malformed push", method: http.MethodPost, event: "push", body: `{"ref":`, signature: sign(`{"ref":`), want: http.StatusBadRequest},
		{name: "oversized", method: http.MethodPost, event: "push", body: oversized, signature: sign(oversized), want: http.StatusRequestEntityTooLarge},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			calls := 0
			receiver := newTestReceiver(t, func(context.Context, PushEvent) error {
				calls++
				return nil
			})
			request := httptest.NewRequest(test.method, "/hooks", strings.NewReader(test.body))
			request.Header.Set("X-GitHub-Event", test.event)
			if test.signature != "" {
				request.Header.Set("X-Hub-Signature-256", test.signature)
			}
			response := httptest.NewRecorder()

			receiver.ServeHTTP(response, request)

			if response.Code != test.want {
				t.Fatalf("status = %d, want %d", response.Code, test.want)
			}
			if calls != 0 {
				t.Fatalf("handler calls = %d, want 0", calls)
			}
		})
	}
}

func TestReceiverAcknowledgesUnsupportedEvent(t *testing.T) {
	calls := 0
	receiver := newTestReceiver(t, func(context.Context, PushEvent) error {
		calls++
		return nil
	})
	request := signedRequest(http.MethodPost, "issues", `{"action":"opened","number":17}`)
	response := httptest.NewRecorder()

	receiver.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusNoContent)
	}
	if calls != 0 {
		t.Fatalf("handler calls = %d, want 0", calls)
	}
}

func TestReceiverReturnsServerErrorWhenHandlerFails(t *testing.T) {
	receiver := newTestReceiver(t, func(context.Context, PushEvent) error {
		return errors.New("downstream unavailable")
	})
	body := `{"ref":"refs/heads/main","repository":{"full_name":"acme/widgets"},"commits":[]}`
	response := httptest.NewRecorder()

	receiver.ServeHTTP(response, signedRequest(http.MethodPost, "push", body))

	if response.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusInternalServerError)
	}
}

func newTestReceiver(t *testing.T, handler PushHandler) *Receiver {
	t.Helper()
	receiver, err := NewReceiver([]byte(testSecret), handler)
	if err != nil {
		t.Fatal(err)
	}
	return receiver
}

func signedRequest(method, event, body string) *http.Request {
	request := httptest.NewRequest(method, "/hooks", strings.NewReader(body))
	request.Header.Set("X-GitHub-Event", event)
	request.Header.Set("X-Hub-Signature-256", sign(body))
	return request
}

func sign(body string) string {
	mac := hmac.New(sha256.New, []byte(testSecret))
	_, _ = mac.Write([]byte(body))
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}
