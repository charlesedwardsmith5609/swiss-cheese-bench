package auditpipe

import "sync"

// Counter stores named monotonic counters.
type Counter interface {
	Inc(name string)
	Value(name string) uint64
}

// MemoryCounter is a concurrency-safe in-memory Counter.
type MemoryCounter struct {
	mu     sync.RWMutex
	values map[string]uint64
}

func NewMemoryCounter() *MemoryCounter {
	return &MemoryCounter{values: make(map[string]uint64)}
}

func (c *MemoryCounter) Inc(name string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.values[name]++
}

func (c *MemoryCounter) Value(name string) uint64 {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.values[name]
}
