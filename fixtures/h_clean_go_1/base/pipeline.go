package auditpipe

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"
)

var ErrInvalidEvent = errors.New("invalid audit event")

type Event struct {
	Actor    string
	Action   string
	Resource string
}

type Processor struct {
	writer  Writer
	counter Counter
	now     func() time.Time
}

func NewProcessor(writer Writer, counter Counter, now func() time.Time) (*Processor, error) {
	if writer == nil {
		return nil, errors.New("audit writer is required")
	}
	if counter == nil {
		return nil, errors.New("counter is required")
	}
	if now == nil {
		now = time.Now
	}
	return &Processor{writer: writer, counter: counter, now: now}, nil
}

func (p *Processor) Process(ctx context.Context, event Event) error {
	if err := validateEvent(event); err != nil {
		return err
	}
	record := AuditRecord{
		Actor:    event.Actor,
		Action:   event.Action,
		Resource: event.Resource,
		At:       p.now().UTC(),
	}
	if err := p.writer.Write(ctx, record); err != nil {
		return fmt.Errorf("write audit record: %w", err)
	}
	p.counter.Inc("audit.records")
	return nil
}

func validateEvent(event Event) error {
	if strings.TrimSpace(event.Actor) == "" {
		return fmt.Errorf("%w: actor is required", ErrInvalidEvent)
	}
	if strings.TrimSpace(event.Action) == "" {
		return fmt.Errorf("%w: action is required", ErrInvalidEvent)
	}
	if strings.TrimSpace(event.Resource) == "" {
		return fmt.Errorf("%w: resource is required", ErrInvalidEvent)
	}
	return nil
}
