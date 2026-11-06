// Package metrics counts pipeline outcomes for the audit log.
package metrics

import "sync"

// Counters are process-local totals. The server owns the set; handlers
// update it while holding no other lock, and tests read a snapshot.
type Counters struct {
	mu       sync.Mutex
	recorded int
	rejected int
	purged   int
}

// New returns zeroed counters.
func New() *Counters {
	return &Counters{}
}

// Record counts one event stored by ingest.
func (c *Counters) Record() {
	c.mu.Lock()
	c.recorded++
	c.mu.Unlock()
}

// Reject records one refused request.
func (c *Counters) Reject() {
	c.mu.Lock()
	c.rejected++
	c.mu.Unlock()
}

// AddPurged adds n events dropped by retention.
func (c *Counters) AddPurged(n int) {
	c.mu.Lock()
	c.purged += n
	c.mu.Unlock()
}

// Snapshot returns recorded, rejected, and purged totals.
func (c *Counters) Snapshot() (recorded, rejected, purged int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.recorded, c.rejected, c.purged
}
