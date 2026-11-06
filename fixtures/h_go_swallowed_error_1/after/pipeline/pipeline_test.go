package pipeline

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
)

type stubRecorder struct {
	recordErr error
	flushErr  error
}

func (r stubRecorder) Record(context.Context, Sample) error { return r.recordErr }
func (r stubRecorder) Flush(context.Context) error          { return r.flushErr }

type stubAuditSink struct {
	appendErr error
	flushErr  error
}

func (s stubAuditSink) Append(context.Context, AuditEntry) error { return s.appendErr }
func (s stubAuditSink) Flush(context.Context) error              { return s.flushErr }

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestObserveRecordsMetricAndAuditEntry(t *testing.T) {
	recorder := &MemoryRecorder{}
	audit := &MemoryAuditSink{}
	p := New(recorder, audit, discardLogger())
	labels := map[string]string{"queue": "fast"}

	if err := p.Observe(context.Background(), "jobs.completed", 3, labels); err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	labels["queue"] = "changed"

	samples := recorder.Samples()
	if len(samples) != 1 {
		t.Fatalf("len(samples) = %d, want 1", len(samples))
	}
	if samples[0].Name != "jobs.completed" || samples[0].Value != 3 {
		t.Fatalf("sample = %#v", samples[0])
	}
	if samples[0].Labels["queue"] != "fast" {
		t.Fatalf("stored labels = %#v", samples[0].Labels)
	}

	entries := audit.Entries()
	if len(entries) != 1 {
		t.Fatalf("len(entries) = %d, want 1", len(entries))
	}
	if entries[0].Action != "metric.recorded" || entries[0].MetricName != "jobs.completed" {
		t.Fatalf("entry = %#v", entries[0])
	}
	if !entries[0].OccurredAt.Equal(samples[0].At) {
		t.Fatalf("audit time %v differs from sample time %v", entries[0].OccurredAt, samples[0].At)
	}
}

func TestObserveReportsAuditAppendFailure(t *testing.T) {
	p := New(
		&MemoryRecorder{},
		stubAuditSink{appendErr: errors.New("audit unavailable")},
		discardLogger(),
	)

	err := p.Observe(context.Background(), "jobs.completed", 1, nil)
	if err == nil {
		t.Fatal("Observe() error = nil")
	}
}

func TestFlushReportsRecorderFailure(t *testing.T) {
	p := New(
		stubRecorder{flushErr: errors.New("metrics unavailable")},
		stubAuditSink{},
		discardLogger(),
	)

	err := p.Flush(context.Background())
	if err == nil {
		t.Fatal("Flush() error = nil")
	}
}
