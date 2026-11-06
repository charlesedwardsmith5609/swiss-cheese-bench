package auth

import (
	"sync"
	"time"
)

// Directory is the process-local session index.
//
// mu guards sessions and hot. Each exported method locks mu for a single
// map update or lookup and releases it before returning. Callers outside
// Directory must not lock mu themselves.
type Directory struct {
	mu       sync.Mutex
	sessions map[string]Session
	hot      *cache
}

// NewDirectory returns an empty index.
func NewDirectory() *Directory {
	return &Directory{
		sessions: make(map[string]Session),
		hot:      newCache(),
	}
}

// Put inserts or replaces s in the index and the hot cache.
func (d *Directory) Put(s Session) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.storeLocked(s)
}

// storeLocked writes s into the index and the hot cache. The caller holds mu.
func (d *Directory) storeLocked(s Session) {
	d.sessions[s.ID] = s
	d.hot.put(s)
}

// Replace deletes prevID from the session map and stores next under one lock.
func (d *Directory) Replace(prevID string, next Session) {
	d.mu.Lock()
	defer d.mu.Unlock()
	delete(d.sessions, prevID)
	d.storeLocked(next)
}

// Get returns the session for id when it exists and now is strictly before
// expiry. A hot-cache hit is preferred so repeated authentications do not
// walk the map.
func (d *Directory) Get(id string, now time.Time) (Session, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if s, ok := d.hot.get(id); ok {
		return checkFresh(s, now)
	}
	s, ok := d.sessions[id]
	if !ok {
		return Session{}, ErrNotFound
	}
	checked, err := checkFresh(s, now)
	if err != nil {
		return Session{}, err
	}
	d.hot.put(checked)
	return checked, nil
}

func checkFresh(s Session, now time.Time) (Session, error) {
	if !now.Before(s.ExpiresAt) {
		return Session{}, ErrExpired
	}
	return s, nil
}

// Retire removes id from the index and from the hot cache.
func (d *Directory) Retire(id string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	delete(d.sessions, id)
	d.hot.drop(id)
}

// Len reports how many sessions the authoritative index holds.
func (d *Directory) Len() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.sessions)
}

// has reports whether id is present in the authoritative index.
func (d *Directory) has(id string) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	_, ok := d.sessions[id]
	return ok
}
