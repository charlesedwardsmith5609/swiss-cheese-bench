package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"strings"
)

const maxPayloadBytes int64 = 1 << 20

type Receiver struct {
	secret     []byte
	handlePush PushHandler
}

func NewReceiver(secret []byte, handlePush PushHandler) (*Receiver, error) {
	if len(secret) == 0 {
		return nil, errors.New("webhook secret is required")
	}
	if handlePush == nil {
		return nil, errors.New("push handler is required")
	}

	secretCopy := append([]byte(nil), secret...)
	return &Receiver{secret: secretCopy, handlePush: handlePush}, nil
}

func (receiver *Receiver) ServeHTTP(response http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		response.Header().Set("Allow", http.MethodPost)
		http.Error(response, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body := http.MaxBytesReader(response, request.Body, maxPayloadBytes)
	payload, err := io.ReadAll(body)
	if err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			http.Error(response, "payload too large", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(response, "unable to read payload", http.StatusBadRequest)
		return
	}

	if !signatureValid(receiver.secret, payload, request.Header.Get("X-Hub-Signature-256")) {
		http.Error(response, "invalid signature", http.StatusUnauthorized)
		return
	}

	eventName := request.Header.Get("X-GitHub-Event")
	if eventName == "" {
		http.Error(response, "event header is required", http.StatusBadRequest)
		return
	}

	switch eventName {
	case "push":
		event, err := decodePush(payload)
		if err != nil {
			http.Error(response, "invalid push payload", http.StatusBadRequest)
			return
		}
		if err := receiver.handlePush(request.Context(), event); err != nil {
			http.Error(response, "handler failed", http.StatusInternalServerError)
			return
		}
	default:
		response.WriteHeader(http.StatusNoContent)
		return
	}

	response.WriteHeader(http.StatusNoContent)
}

func signatureValid(secret, payload []byte, signature string) bool {
	const prefix = "sha256="
	if !strings.HasPrefix(signature, prefix) || len(signature) != len(prefix)+sha256.Size*2 {
		return false
	}

	provided, err := hex.DecodeString(signature[len(prefix):])
	if err != nil {
		return false
	}

	mac := hmac.New(sha256.New, secret)
	_, _ = mac.Write(payload)
	return hmac.Equal(provided, mac.Sum(nil))
}
