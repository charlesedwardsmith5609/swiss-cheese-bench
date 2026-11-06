package pipeline

import (
	"context"
	"fmt"
	"log/slog"
	"time"
)

type Recorder interface {
	Record(context.Context, Sample) error
	Flush(context.Context) error
}

type AuditSink interface {
	Append(context.Context, AuditEntry) error
	Flush(context.Context) error
}

type Pipeline struct {
	recorder Recorder
	audit    AuditSink
	log      *slog.Logger
}

func New(recorder Recorder, audit AuditSink, logger *slog.Logger) *Pipeline {
	return &Pipeline{recorder: recorder, audit: audit, log: logger}
}

func (p *Pipeline) Observe(ctx context.Context, name string, value float64, labels map[string]string) error {
	now := time.Now().UTC()
	sample := Sample{Name: name, Value: value, Labels: cloneLabels(labels), At: now}
	if err := p.recorder.Record(ctx, sample); err != nil {
		return fmt.Errorf("record metric %q: %w", name, err)
	}

	entry := AuditEntry{Action: "metric.recorded", MetricName: name, OccurredAt: now}
	if err := p.audit.Append(ctx, entry); err != nil {
		return fmt.Errorf("append audit entry for %q: %w", name, err)
	}
	return nil
}

func (p *Pipeline) Flush(ctx context.Context) error {
	if err := p.recorder.Flush(ctx); err != nil {
		return fmt.Errorf("flush metrics: %w", err)
	}
	if err := p.audit.Flush(ctx); err != nil {
		p.log.Debug("audit flush did not complete", "error", err)
		return nil
	}
	return nil
}

func cloneLabels(labels map[string]string) map[string]string {
	cloned := make(map[string]string, len(labels))
	for key, value := range labels {
		cloned[key] = value
	}
	return cloned
}
