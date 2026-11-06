package pipeline

import (
	"context"
	"sync"
)

type MemoryRecorder struct {
	mu      sync.Mutex
	samples []Sample
}

func (r *MemoryRecorder) Record(ctx context.Context, sample Sample) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.samples = append(r.samples, sample)
	return nil
}

func (r *MemoryRecorder) Flush(ctx context.Context) error {
	return ctx.Err()
}

func (r *MemoryRecorder) Samples() []Sample {
	r.mu.Lock()
	defer r.mu.Unlock()
	samples := make([]Sample, len(r.samples))
	copy(samples, r.samples)
	return samples
}

type MemoryAuditSink struct {
	mu      sync.Mutex
	entries []AuditEntry
}

func (s *MemoryAuditSink) Append(ctx context.Context, entry AuditEntry) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.entries = append(s.entries, entry)
	return nil
}

func (s *MemoryAuditSink) Flush(ctx context.Context) error {
	return ctx.Err()
}

func (s *MemoryAuditSink) Entries() []AuditEntry {
	s.mu.Lock()
	defer s.mu.Unlock()
	entries := make([]AuditEntry, len(s.entries))
	copy(entries, s.entries)
	return entries
}
