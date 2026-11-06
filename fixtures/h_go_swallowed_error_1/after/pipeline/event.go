package pipeline

import "time"

// Sample is a metric measurement accepted by the pipeline.
type Sample struct {
	Name   string
	Value  float64
	Labels map[string]string
	At     time.Time
}

// AuditEntry describes the ingestion of a metric sample.
type AuditEntry struct {
	Action     string
	MetricName string
	OccurredAt time.Time
}
