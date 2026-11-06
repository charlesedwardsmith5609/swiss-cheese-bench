package workq

import (
	"testing"
	"time"
)

func TestQueueReadyJobsRemainFIFO(t *testing.T) {
	var queue Queue
	now := time.Date(2026, time.November, 6, 12, 0, 0, 0, time.UTC)
	if err := queue.Schedule(Job{ID: "scheduled-first"}, now.Add(time.Minute)); err != nil {
		t.Fatalf("schedule first: %v", err)
	}
	if err := queue.Enqueue(Job{ID: "immediate-second"}); err != nil {
		t.Fatalf("enqueue second: %v", err)
	}

	job, ok := queue.DequeueReady(now.Add(time.Minute))
	if !ok || job.ID != "scheduled-first" {
		t.Fatalf("first dequeue = %#v, %v", job, ok)
	}
	job, ok = queue.DequeueReady(now.Add(time.Minute))
	if !ok || job.ID != "immediate-second" {
		t.Fatalf("second dequeue = %#v, %v", job, ok)
	}
}

func TestQueueSkipsJobsThatAreNotReady(t *testing.T) {
	var queue Queue
	now := time.Date(2026, time.November, 6, 12, 0, 0, 0, time.UTC)
	if err := queue.Schedule(Job{ID: "later"}, now.Add(time.Hour)); err != nil {
		t.Fatalf("schedule: %v", err)
	}
	if _, ok := queue.DequeueReady(now); ok {
		t.Fatal("dequeued a job before its ready time")
	}
	if queue.Len() != 1 {
		t.Fatalf("length = %d, want 1", queue.Len())
	}
}

func TestScheduleReportsMissingID(t *testing.T) {
	var queue Queue
	if err := queue.Schedule(Job{}, time.Now()); err == nil {
		t.Fatal("expected a scheduling error")
	}
}
