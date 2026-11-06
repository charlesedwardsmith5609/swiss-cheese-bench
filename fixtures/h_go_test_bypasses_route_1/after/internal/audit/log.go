// Package audit stores operational events for the metrics pipeline.
package audit

import (
	"sync"
	"time"
)

// Event is one recorded action in the pipeline.
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
	return l.Query("", time.Time{})
}

// Query returns events for actor, or all actors when actor is empty,
// at or after since. A zero since matches every timestamp.
func (l *Log) Query(actor string, since time.Time) []Event {
	l.mu.Lock()
	defer l.mu.Unlock()
	out := make([]Event, 0, len(l.events))
	for _, e := range l.events {
		if actor != "" && e.Actor != actor {
			continue
		}
		if !since.IsZero() && e.At.Before(since) {
			continue
		}
		out = append(out, e)
	}
	return out
}

// PurgeBefore removes events older than t and returns how many were dropped.
func (l *Log) PurgeBefore(t time.Time) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	kept := make([]Event, 0, len(l.events))
	for _, e := range l.events {
		if !e.At.Before(t) {
			kept = append(kept, e)
		}
	}
	removed := len(l.events) - len(kept)
	l.events = kept
	return removed
}
