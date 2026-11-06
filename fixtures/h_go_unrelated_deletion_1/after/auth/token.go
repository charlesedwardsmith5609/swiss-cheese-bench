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
// IdleDeadline slides; AbsoluteExpiry is fixed at issue time.
type Snapshot struct {
	ID             string    `json:"id"`
	UserID         string    `json:"user_id"`
	IdleDeadline   time.Time `json:"idle_deadline"`
	AbsoluteExpiry time.Time `json:"absolute_expiry"`
	IssuedAt       time.Time `json:"issued_at"`
}

// SnapshotOf copies the exported session fields.
func SnapshotOf(sess *Session) Snapshot {
	return Snapshot{
		ID:             sess.ID,
		UserID:         sess.UserID,
		IdleDeadline:   sess.IdleDeadline,
		AbsoluteExpiry: sess.AbsoluteExpiry,
		IssuedAt:       sess.IssuedAt,
	}
}

// TokenCodec seals a session id with HMAC-SHA256. The key is copied at construction.
type TokenCodec struct {
	secret []byte
}

// NewTokenCodec copies secret so a later edit by the caller cannot change the key.
func NewTokenCodec(secret []byte) *TokenCodec {
	cp := make([]byte, len(secret))
	copy(cp, secret)
	return &TokenCodec{secret: cp}
}

// Seal returns the session id and its hex HMAC, separated by a dot.
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
	id, macHex, ok := strings.Cut(raw, ".")
	if !ok || id == "" || macHex == "" {
		return "", ErrToken
	}
	want, err := hex.DecodeString(macHex)
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
