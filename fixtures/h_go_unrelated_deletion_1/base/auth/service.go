package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"
)

const (
	tokenBytes = 32
	lifetime   = 12 * time.Hour
)

// Log retains authentication events in memory, in call order.
// The Service calls Log on the request goroutine. A nil Log discards events.
type Log struct {
	events []Event
}

// NewLog returns an empty log.
func NewLog() *Log {
	return &Log{}
}

// Record appends one event.
func (l *Log) Record(action, userID, sessionID string) {
	if l == nil {
		return
	}
	l.events = append(l.events, Event{
		Action:    action,
		UserID:    userID,
		SessionID: sessionID,
	})
}

// Events returns a copy of the recorded events.
func (l *Log) Events() []Event {
	if l == nil {
		return nil
	}
	out := make([]Event, len(l.events))
	copy(out, l.events)
	return out
}

// Service issues and checks session credentials.
type Service struct {
	dir *Directory
	log *Log
}

// NewService returns a service that stores sessions in dir and events in log.
func NewService(dir *Directory, log *Log) *Service {
	return &Service{dir: dir, log: log}
}

// Login issues a session for userID. now is the caller's clock, used for
// expiry and LastSeen so tests can freeze time.
func (s *Service) Login(userID string, now time.Time) (Session, string, error) {
	if userID == "" {
		return Session{}, "", ErrCredentials
	}
	sess, raw, err := s.issue(userID, now)
	if err != nil {
		return Session{}, "", err
	}
	s.dir.Put(sess)
	s.log.Record("session.login", userID, sess.ID)
	return sess, raw, nil
}

// Refresh exchanges a live session for a new id, token, and expiry. The user
// is unchanged. The previous record is removed before the successor is stored.
func (s *Service) Refresh(id, token string, now time.Time) (Session, string, error) {
	cur, err := s.dir.Get(id, now)
	if err != nil {
		return Session{}, "", err
	}
	if cur.TokenHash != hashToken(token) {
		return Session{}, "", ErrCredentials
	}
	fresh, raw, err := s.issue(cur.UserID, now)
	if err != nil {
		return Session{}, "", err
	}
	s.dir.mu.Lock()
	delete(s.dir.sessions, cur.ID)
	s.dir.hot.drop(cur.ID)
	s.dir.sessions[fresh.ID] = fresh
	s.dir.hot.put(fresh)
	s.dir.mu.Unlock()
	s.log.Record("session.refresh", cur.UserID, fresh.ID)
	return fresh, raw, nil
}

// Logout retires id if it is present. A second logout is a no-op.
func (s *Service) Logout(id string) {
	s.dir.Retire(id)
	s.log.Record("session.logout", "", id)
}

// Authenticate checks the bearer token against the stored hash and expiry.
func (s *Service) Authenticate(id, token string, now time.Time) (Principal, error) {
	cur, err := s.dir.Get(id, now)
	if err != nil {
		return Principal{}, err
	}
	if cur.TokenHash != hashToken(token) {
		return Principal{}, ErrCredentials
	}
	return Principal{UserID: cur.UserID, SessionID: cur.ID}, nil
}

// issue builds an unstored session and the raw bearer token.
func (s *Service) issue(userID string, now time.Time) (Session, string, error) {
	id, err := newID()
	if err != nil {
		return Session{}, "", err
	}
	raw, err := newToken()
	if err != nil {
		return Session{}, "", err
	}
	sess := Session{
		ID:        id,
		UserID:    userID,
		TokenHash: hashToken(raw),
		ExpiresAt: now.Add(lifetime),
		LastSeen:  now,
	}
	return sess, raw, nil
}

// hashToken is the hex SHA-256 of the raw bearer token.
func hashToken(raw string) string {
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
