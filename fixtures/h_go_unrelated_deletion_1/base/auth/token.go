package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
	"time"
)

// ErrToken is returned when a session cookie fails to verify.
var ErrToken = errors.New("auth: bad session token")

// Snapshot is the session view handlers return to clients.
type Snapshot struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	ExpiresAt time.Time `json:"expires_at"`
	IssuedAt  time.Time `json:"issued_at"`
}

// SnapshotOf copies the exported session fields.
func SnapshotOf(sess *Session) Snapshot {
	return Snapshot{
		ID:        sess.ID,
		UserID:    sess.UserID,
		ExpiresAt: sess.ExpiresAt,
		IssuedAt:  sess.IssuedAt,
	}
}

// TokenCodec seals a session id with HMAC-SHA256.
type TokenCodec struct {
	secret []byte
}

// NewTokenCodec copies secret so a later edit by the caller cannot change the key.
func NewTokenCodec(secret []byte) *TokenCodec {
	cp := make([]byte, len(secret))
	copy(cp, secret)
	return &TokenCodec{secret: cp}
}

// Seal returns the session id and a hex HMAC, separated by a dot.
func (c *TokenCodec) Seal(id string) (string, error) {
	if id == "" {
		return "", ErrToken
	}
	mac := hmac.New(sha256.New, c.secret)
	if _, err := mac.Write([]byte(id)); err != nil {
		return "", err
	}
	return id + "." + hex.EncodeToString(mac.Sum(nil)), nil
}

// Open checks the HMAC and returns the session id.
func (c *TokenCodec) Open(raw string) (string, error) {
	id, sig, ok := strings.Cut(raw, ".")
	if !ok || id == "" || sig == "" {
		return "", ErrToken
	}
	want, err := hex.DecodeString(sig)
	if err != nil {
		return "", ErrToken
	}
	mac := hmac.New(sha256.New, c.secret)
	if _, err := mac.Write([]byte(id)); err != nil {
		return "", err
	}
	if !hmac.Equal(mac.Sum(nil), want) {
		return "", ErrToken
	}
	return id, nil
}
