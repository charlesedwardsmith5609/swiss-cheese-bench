// Package metrics counts pipeline outcomes for the audit log.
package metrics

import "sync"

// Counters are process-local totals. The server owns the set; handlers
// update it while holding no other lock, and tests read a snapshot.
type Counters struct {
	mu       sync.Mutex
	accepted int
	rejected int
}

// New returns zeroed counters.
func New() *Counters {
	return &Counters{}
}

// Accept records one stored event.
func (c *Counters) Accept() {
	c.mu.Lock()
	c.accepted++
	c.mu.Unlock()
}

// Reject records one refused request.
func (c *Counters) Reject() {
	c.mu.Lock()
	c.rejected++
	c.mu.Unlock()
}

// Snapshot returns accepted and rejected totals.
func (c *Counters) Snapshot() (accepted, rejected int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.accepted, c.rejected
}
