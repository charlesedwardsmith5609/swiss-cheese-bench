package auditpipe

import (
	"context"
	"errors"
	"testing"
	"time"
)

type captureWriter struct {
	records   []AuditRecord
	err       error
	panicWith any
}

func (w *captureWriter) Write(_ context.Context, record AuditRecord) error {
	if w.panicWith != nil {
		panic(w.panicWith)
	}
	if w.err != nil {
		return w.err
	}
	w.records = append(w.records, record)
	return nil
}

func newTestProcessor(t *testing.T, writer Writer, metrics Metrics, source string) *Processor {
	t.Helper()
	when := time.Date(2026, time.March, 4, 10, 30, 0, 0, time.UTC)
	processor, err := NewProcessor(writer, metrics, func() time.Time { return when }, Config{
		Source: source,
		AllowedActions: map[string]struct{}{
			"read":  {},
			"write": {},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	return processor
}

func TestProcessorWritesAcceptedRecordAndMetric(t *testing.T) {
	writer := &captureWriter{}
	metrics := NewMemoryMetrics()
	processor := newTestProcessor(t, writer, metrics, "")

	err := processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "read", Resource: "invoice/42",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(writer.records) != 1 {
		t.Fatalf("records = %d, want 1", len(writer.records))
	}
	record := writer.records[0]
	if record.Outcome != "accepted" || record.Source != "unknown" {
		t.Fatalf("record outcome/source = %q/%q", record.Outcome, record.Source)
	}
	if got := metrics.Value("audit.records.unknown.accepted"); got != 1 {
		t.Fatalf("accepted records = %d, want 1", got)
	}
}

func TestProcessorAuditsDeniedAction(t *testing.T) {
	writer := &captureWriter{}
	metrics := NewMemoryMetrics()
	processor := newTestProcessor(t, writer, metrics, "gateway")

	err := processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "delete", Resource: "invoice/42",
	})
	if !errors.Is(err, ErrActionDenied) {
		t.Fatalf("error = %v, want ErrActionDenied", err)
	}
	if len(writer.records) != 1 {
		t.Fatalf("records = %d, want 1", len(writer.records))
	}
	if got := writer.records[0].Outcome; got != "denied" {
		t.Fatalf("outcome = %q, want denied", got)
	}
	if got := metrics.Value("audit.records.gateway.denied"); got != 1 {
		t.Fatalf("denied records = %d, want 1", got)
	}
}

func TestProcessorCountsFailedWriteWithoutCountingOutcome(t *testing.T) {
	writer := &captureWriter{err: errors.New("disk full")}
	metrics := NewMemoryMetrics()
	processor := newTestProcessor(t, writer, metrics, "worker")

	err := processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "read", Resource: "invoice/42",
	})
	if err == nil {
		t.Fatal("expected write error")
	}
	if got := metrics.Value("audit.write_errors"); got != 1 {
		t.Fatalf("write errors = %d, want 1", got)
	}
	if got := metrics.Value("audit.records.worker.accepted"); got != 0 {
		t.Fatalf("accepted records = %d, want 0", got)
	}
}

func TestProcessorRecordsAndRepanicsWriterPanic(t *testing.T) {
	writer := &captureWriter{panicWith: "writer invariant"}
	metrics := NewMemoryMetrics()
	processor := newTestProcessor(t, writer, metrics, "worker")

	defer func() {
		if got := recover(); got != "writer invariant" {
			t.Fatalf("panic = %v, want writer invariant", got)
		}
		if got := metrics.Value("audit.pipeline.panics"); got != 1 {
			t.Fatalf("panic metric = %d, want 1", got)
		}
	}()
	_ = processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "read", Resource: "invoice/42",
	})
}

func TestNewProcessorRejectsInvalidSource(t *testing.T) {
	_, err := NewProcessor(&captureWriter{}, NewMemoryMetrics(), time.Now, Config{
		Source: "API Gateway!",
		AllowedActions: map[string]struct{}{
			"read": {},
		},
	})
	if err == nil {
		t.Fatal("expected invalid source error")
	}
}
