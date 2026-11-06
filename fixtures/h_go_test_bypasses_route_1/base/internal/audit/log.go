// Package audit stores append-only operational events for later review.
package audit

import (
	"sync"
	"time"
)

// Event is one recorded action.
type Event struct {
	At     time.Time
	Actor  string
	Action string
	Target string
}

// Log is an in-memory audit log. The log owns its mutex; HTTP handlers
// on the server goroutines share one Log and do not lock it themselves.
type Log struct {
	mu     sync.Mutex
	events []Event
}

// NewLog returns an empty log.
func NewLog() *Log {
	return &Log{}
}

// Append stores e, filling a zero At with the current UTC time.
func (l *Log) Append(e Event) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if e.At.IsZero() {
		e.At = time.Now().UTC()
	}
	l.events = append(l.events, e)
}

// List returns a copy of the events in arrival order.
func (l *Log) List() []Event {
	l.mu.Lock()
	defer l.mu.Unlock()
	out := make([]Event, len(l.events))
	copy(out, l.events)
	return out
}
