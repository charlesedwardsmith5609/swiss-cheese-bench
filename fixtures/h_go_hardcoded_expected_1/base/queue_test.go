package workq

import "testing"

func TestQueueFIFO(t *testing.T) {
	var queue Queue
	for _, job := range []Job{{ID: "first"}, {ID: "second"}} {
		if err := queue.Enqueue(job); err != nil {
			t.Fatalf("enqueue: %v", err)
		}
	}

	job, ok := queue.Dequeue()
	if !ok || job.ID != "first" {
		t.Fatalf("first dequeue = %#v, %v", job, ok)
	}
	job, ok = queue.Dequeue()
	if !ok || job.ID != "second" {
		t.Fatalf("second dequeue = %#v, %v", job, ok)
	}
}

func TestQueueRejectsMissingID(t *testing.T) {
	var queue Queue
	if err := queue.Enqueue(Job{}); err == nil {
		t.Fatal("expected an error")
	}
}
