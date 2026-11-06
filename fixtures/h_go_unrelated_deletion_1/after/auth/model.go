// Package auth issues and checks process-local login sessions.
//
// A Service stores Session values in a Directory and appends Event values to
// a Log. Login records the OAuth client id. Refresh keeps that client and
// the user, and mints a new session id, bearer token, and absolute expiry.
// Both paths stamp TouchedAt from the caller-supplied clock. The raw bearer
// token is returned once and is not written to the Directory.
package auth

import (
	"errors"
	"time"
)

var (
	// ErrNotFound means the session id is not in the index.
	ErrNotFound = errors.New("auth: session not found")

	// ErrExpired means now is at or past the session's absolute expiry.
	ErrExpired = errors.New("auth: session expired")

	// ErrCredentials means the user id, client id, or bearer token was rejected.
	ErrCredentials = errors.New("auth: credentials rejected")
)

// Session is the server-side record of one authenticated login.
// The bearer token is not retained. TokenHash is a hex-encoded SHA-256 of it.
// ClientID is the OAuth client that started the login. TouchedAt is the
// caller-supplied clock at mint time, for both login and refresh.
type Session struct {
	ID        string
	UserID    string
	ClientID  string
	TokenHash string
	ExpiresAt time.Time
	TouchedAt time.Time
}

// Principal is the identity a handler receives after Authenticate succeeds.
type Principal struct {
	UserID    string
	SessionID string
}

// Event is one authentication action kept for operators.
type Event struct {
	Action    string
	UserID    string
	SessionID string
}
