package auditpipe

import "sync"

// Metrics stores named monotonic measurements.
type Metrics interface {
	Add(name string, delta uint64)
	Value(name string) uint64
}

// MemoryMetrics is a concurrency-safe in-memory Metrics implementation.
type MemoryMetrics struct {
	mu     sync.RWMutex
	values map[string]uint64
}

func NewMemoryMetrics() *MemoryMetrics {
	return &MemoryMetrics{values: make(map[string]uint64)}
}

func (m *MemoryMetrics) Add(name string, delta uint64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.values[name] += delta
}

func (m *MemoryMetrics) Value(name string) uint64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.values[name]
}

func (m *MemoryMetrics) Snapshot() map[string]uint64 {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make(map[string]uint64, len(m.values))
	for name, value := range m.values {
		result[name] = value
	}
	return result
}
