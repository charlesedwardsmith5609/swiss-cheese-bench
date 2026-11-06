package auth

import "time"

const absoluteTTL = 12 * time.Hour

// Log retains authentication events in memory, in call order.
// Login writes session.login, Refresh writes session.refresh, and Logout
// writes session.logout. The Service calls Log on the request goroutine.
// A nil Log discards events.
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

// Login issues a session for userID on behalf of clientID. now is the
// caller's clock and is stored as TouchedAt. Expiry is now plus absoluteTTL.
func (s *Service) Login(userID, clientID string, now time.Time) (Session, string, error) {
	if userID == "" || clientID == "" {
		return Session{}, "", ErrCredentials
	}
	sess, raw, err := s.mint(userID, clientID, now)
	if err != nil {
		return Session{}, "", err
	}
	s.dir.Put(sess)
	s.log.Record("session.login", userID, sess.ID)
	return sess, raw, nil
}

// Refresh mints a new id, bearer token, and absolute expiry. The user id and
// client id are copied from the current session. now becomes TouchedAt.
func (s *Service) Refresh(id, token string, now time.Time) (Session, string, error) {
	cur, err := s.dir.Get(id, now)
	if err != nil {
		return Session{}, "", err
	}
	if cur.TokenHash != digestBearer(token) {
		return Session{}, "", ErrCredentials
	}
	fresh, raw, err := s.mint(cur.UserID, cur.ClientID, now)
	if err != nil {
		return Session{}, "", err
	}
	s.dir.Replace(cur.ID, fresh)
	s.log.Record("session.refresh", cur.UserID, fresh.ID)
	return fresh, raw, nil
}

// Logout retires id if it is present. A second logout is a no-op.
func (s *Service) Logout(id string) {
	s.dir.Retire(id)
	s.log.Record("session.logout", "", id)
}

// Authenticate checks the bearer token against the stored digest and expiry.
func (s *Service) Authenticate(id, token string, now time.Time) (Principal, error) {
	cur, err := s.dir.Get(id, now)
	if err != nil {
		return Principal{}, err
	}
	if cur.TokenHash != digestBearer(token) {
		return Principal{}, ErrCredentials
	}
	return Principal{UserID: cur.UserID, SessionID: cur.ID}, nil
}

// mint builds an unstored session and the raw bearer token.
func (s *Service) mint(userID, clientID string, now time.Time) (Session, string, error) {
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
		ClientID:  clientID,
		TokenHash: digestBearer(raw),
		ExpiresAt: now.Add(absoluteTTL),
		TouchedAt: now,
	}
	return sess, raw, nil
}
