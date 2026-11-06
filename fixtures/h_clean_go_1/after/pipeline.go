package auditpipe

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

var (
	ErrActionDenied = errors.New("action denied")
	ErrInvalidEvent = errors.New("invalid audit event")
	validSource     = regexp.MustCompile(`^[a-z][a-z0-9_-]{0,31}$`)
)

type Event struct {
	Actor    string
	Action   string
	Resource string
}

type Config struct {
	Source         string
	AllowedActions map[string]struct{}
}

type Processor struct {
	writer         Writer
	metrics        Metrics
	now            func() time.Time
	source         string
	allowedActions map[string]struct{}
}

func NewProcessor(writer Writer, metrics Metrics, now func() time.Time, cfg Config) (*Processor, error) {
	if writer == nil {
		return nil, errors.New("audit writer is required")
	}
	if metrics == nil {
		return nil, errors.New("metrics sink is required")
	}
	if now == nil {
		now = time.Now
	}

	source := canonicalSource(cfg.Source)
	if !validSource.MatchString(source) {
		return nil, fmt.Errorf("invalid audit source %q", cfg.Source)
	}
	if len(cfg.AllowedActions) == 0 {
		return nil, errors.New("at least one allowed action is required")
	}
	allowed := make(map[string]struct{}, len(cfg.AllowedActions))
	for action := range cfg.AllowedActions {
		if action == "" || action != strings.TrimSpace(action) {
			return nil, fmt.Errorf("invalid allowed action %q", action)
		}
		allowed[action] = struct{}{}
	}

	return &Processor{
		writer: writer, metrics: metrics, now: now,
		source: source, allowedActions: allowed,
	}, nil
}

func (p *Processor) Process(ctx context.Context, event Event) error {
	defer p.recordPanic()

	if err := validateEvent(event); err != nil {
		return err
	}
	outcome := "accepted"
	if _, ok := p.allowedActions[event.Action]; !ok {
		outcome = "denied"
	}
	record := AuditRecord{
		Actor: event.Actor, Action: event.Action, Resource: event.Resource,
		Outcome: outcome, Source: p.source, At: p.now().UTC(),
	}
	if err := p.writer.Write(ctx, record); err != nil {
		p.metrics.Add("audit.write_errors", 1)
		return fmt.Errorf("write audit record: %w", err)
	}
	p.metrics.Add(fmt.Sprintf("audit.records.%s.%s", p.source, outcome), 1)
	if outcome == "denied" {
		return fmt.Errorf("%w: %s", ErrActionDenied, event.Action)
	}
	return nil
}

func (p *Processor) recordPanic() {
	recovered := recover()
	if recovered == nil {
		return
	}
	p.metrics.Add("audit.pipeline.panics", 1)
	panic(recovered)
}

func canonicalSource(source string) string {
	source = strings.TrimSpace(source)
	if source == "" {
		return "unknown"
	}
	return source
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
