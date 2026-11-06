package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

// tokenBytes is the raw bearer token length before hex encoding.
const tokenBytes = 32

// digestBearer is the hex SHA-256 of the raw bearer token.
func digestBearer(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

// newID returns a random 128-bit session id as hex.
func newID() (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("auth: id: %w", err)
	}
	return hex.EncodeToString(buf), nil
}

// newToken returns a random bearer token as hex.
func newToken() (string, error) {
	buf := make([]byte, tokenBytes)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("auth: token: %w", err)
	}
	return hex.EncodeToString(buf), nil
}
