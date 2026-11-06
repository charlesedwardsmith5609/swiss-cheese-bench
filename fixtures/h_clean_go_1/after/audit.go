package auditpipe

import (
	"context"
	"encoding/json"
	"io"
	"sync"
	"time"
)

// AuditRecord is the durable representation of an action and its outcome.
type AuditRecord struct {
	Actor    string    `json:"actor"`
	Action   string    `json:"action"`
	Resource string    `json:"resource"`
	Outcome  string    `json:"outcome"`
	Source   string    `json:"source"`
	At       time.Time `json:"at"`
}

type Writer interface {
	Write(context.Context, AuditRecord) error
}

// JSONWriter serializes one record per line.
type JSONWriter struct {
	mu  sync.Mutex
	dst io.Writer
}

func NewJSONWriter(dst io.Writer) *JSONWriter {
	return &JSONWriter{dst: dst}
}

func (w *JSONWriter) Write(_ context.Context, record AuditRecord) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	return json.NewEncoder(w.dst).Encode(record)
}
