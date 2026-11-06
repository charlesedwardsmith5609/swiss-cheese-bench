package auth

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"sync"
	"time"
)

const (
	idBytes     = 16
	maxSessions = 10000
	maxDevices  = 8
)

// ErrNotFound means the id is not in the store.
// ErrExpired means the idle deadline has passed.
// ErrStoreFull and ErrTooMany bound how many sessions are retained.
var (
	ErrNotFound  = errors.New("auth: session not found")
	ErrExpired   = errors.New("auth: session expired")
	ErrStoreFull = errors.New("auth: session store is full")
	ErrTooMany   = errors.New("auth: too many sessions for user")
)

// Session is one signed-in device. ExpiresAt is the idle deadline.
type Session struct {
	ID        string
	UserID    string
	ExpiresAt time.Time
	IssuedAt  time.Time
}

// Store is an in-memory session table. Store owns its mutex.
type Store struct {
	mu       sync.Mutex
	sessions map[string]*Session
	byUser   map[string][]string
	now      func() time.Time
	idle     time.Duration
}

// NewStore returns a store whose sessions go idle after idle.
func NewStore(idle time.Duration) *Store {
	return &Store{
		sessions: make(map[string]*Session),
		byUser:   make(map[string][]string),
		now:      time.Now,
		idle:     idle,
	}
}

// Issue opens a session for userID and appends it to that user's device list.
func (s *Store) Issue(userID string) (*Session, error) {
	if userID == "" {
		return nil, errors.New("auth: empty user id")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.sessions) >= maxSessions {
		return nil, ErrStoreFull
	}
	list := s.byUser[userID]
	if len(list) >= maxDevices {
		return nil, ErrTooMany
	}
	id, err := newSessionID()
	if err != nil {
		return nil, err
	}
	now := s.clock()
	sess := &Session{
		ID:        id,
		UserID:    userID,
		ExpiresAt: now.Add(s.idle),
		IssuedAt:  now,
	}
	s.sessions[id] = sess
	s.byUser[userID] = append(list, id)
	return cloneSession(sess), nil
}

// Get returns a live session. An expired session is removed.
func (s *Store) Get(id string) (*Session, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, err := s.liveLocked(id)
	if err != nil {
		return nil, err
	}
	return cloneSession(sess), nil
}

// Touch extends the idle deadline of a live session.
func (s *Store) Touch(id string) (*Session, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, err := s.liveLocked(id)
	if err != nil {
		return nil, err
	}
	sess.ExpiresAt = s.clock().Add(s.idle)
	return cloneSession(sess), nil
}

// Revoke deletes the session and its device-list entry.
func (s *Store) Revoke(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[id]
	if !ok {
		return ErrNotFound
	}
	s.dropLocked(sess)
	return nil
}

// EndDevice revokes the session at index in the user's device list.
// Index zero is the oldest session still on file for that user.
// An expired session is dropped and reported as ErrExpired.
func (s *Store) EndDevice(userID string, index int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	list := s.byUser[userID]
	if index < 0 || index >= len(list) {
		return ErrNotFound
	}
	sess, ok := s.sessions[list[index]]
	if !ok {
		return ErrNotFound
	}
	if s.clock().After(sess.ExpiresAt) {
		s.dropLocked(sess)
		return ErrExpired
	}
	s.dropLocked(sess)
	return nil
}

// Devices returns the user's sessions, oldest first.
func (s *Store) Devices(userID string) []*Session {
	s.mu.Lock()
	defer s.mu.Unlock()
	list := s.byUser[userID]
	out := make([]*Session, 0, len(list))
	for _, id := range list {
		sess, ok := s.sessions[id]
		if !ok {
			continue
		}
		out = append(out, cloneSession(sess))
	}
	return out
}

func (s *Store) liveLocked(id string) (*Session, error) {
	sess, ok := s.sessions[id]
	if !ok {
		return nil, ErrNotFound
	}
	if s.clock().After(sess.ExpiresAt) {
		s.dropLocked(sess)
		return nil, ErrExpired
	}
	return sess, nil
}

func (s *Store) dropLocked(sess *Session) {
	delete(s.sessions, sess.ID)
	list := s.byUser[sess.UserID]
	for i, id := range list {
		if id != sess.ID {
			continue
		}
		s.byUser[sess.UserID] = append(list[:i], list[i+1:]...)
		break
	}
	if len(s.byUser[sess.UserID]) == 0 {
		delete(s.byUser, sess.UserID)
	}
}

func (s *Store) clock() time.Time {
	if s.now == nil {
		return time.Now()
	}
	return s.now()
}

func cloneSession(sess *Session) *Session {
	cp := *sess
	return &cp
}

func newSessionID() (string, error) {
	buf := make([]byte, idBytes)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}
