package pipeline

import (
	"context"
	"errors"
	"testing"
)

type failingRecorder struct {
	err error
}

func (r failingRecorder) Record(context.Context, metricPoint) error {
	return r.err
}

func TestObserveRecordsMetric(t *testing.T) {
	recorder := &MemoryRecorder{}
	p := New(recorder)

	if err := p.Observe(context.Background(), "jobs.completed", 3, map[string]string{"queue": "fast"}); err != nil {
		t.Fatalf("Observe() error = %v", err)
	}

	points := recorder.Points()
	if len(points) != 1 {
		t.Fatalf("len(points) = %d, want 1", len(points))
	}
	if points[0].Name != "jobs.completed" || points[0].Value != 3 {
		t.Fatalf("point = %#v", points[0])
	}
}

func TestObserveReportsRecorderFailure(t *testing.T) {
	p := New(failingRecorder{err: errors.New("offline")})

	err := p.Observe(context.Background(), "jobs.completed", 1, nil)
	if err == nil {
		t.Fatal("Observe() error = nil")
	}
}
