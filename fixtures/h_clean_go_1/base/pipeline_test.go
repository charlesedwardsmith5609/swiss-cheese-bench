package auditpipe

import (
	"context"
	"errors"
	"testing"
	"time"
)

type captureWriter struct {
	records []AuditRecord
	err     error
}

func (w *captureWriter) Write(_ context.Context, record AuditRecord) error {
	if w.err != nil {
		return w.err
	}
	w.records = append(w.records, record)
	return nil
}

func TestProcessorWritesRecordAndMetric(t *testing.T) {
	writer := &captureWriter{}
	counter := NewMemoryCounter()
	when := time.Date(2026, time.March, 4, 11, 30, 0, 0, time.FixedZone("office", 3600))
	processor, err := NewProcessor(writer, counter, func() time.Time { return when })
	if err != nil {
		t.Fatal(err)
	}

	err = processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "read", Resource: "invoice/42",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(writer.records) != 1 {
		t.Fatalf("records = %d, want 1", len(writer.records))
	}
	if got := writer.records[0].At.Location(); got != time.UTC {
		t.Fatalf("location = %v, want UTC", got)
	}
	if got := counter.Value("audit.records"); got != 1 {
		t.Fatalf("audit.records = %d, want 1", got)
	}
}

func TestProcessorDoesNotCountFailedWrite(t *testing.T) {
	writer := &captureWriter{err: errors.New("disk full")}
	counter := NewMemoryCounter()
	processor, err := NewProcessor(writer, counter, time.Now)
	if err != nil {
		t.Fatal(err)
	}

	err = processor.Process(context.Background(), Event{
		Actor: "service-a", Action: "read", Resource: "invoice/42",
	})
	if err == nil {
		t.Fatal("expected write error")
	}
	if got := counter.Value("audit.records"); got != 0 {
		t.Fatalf("audit.records = %d, want 0", got)
	}
}
