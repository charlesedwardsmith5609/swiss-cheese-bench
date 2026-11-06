package workq

import (
	"errors"
	"sync"
)

// Job is one unit of work accepted by a Queue.
type Job struct {
	ID      string
	Payload string
}

// Queue is a concurrency-safe in-memory FIFO.
type Queue struct {
	mu    sync.Mutex
	items []Job
}

// Enqueue appends a job to the queue.
func (q *Queue) Enqueue(job Job) error {
	if job.ID == "" {
		return errors.New("job ID is required")
	}

	q.mu.Lock()
	defer q.mu.Unlock()
	q.items = append(q.items, job)
	return nil
}

// Dequeue removes the oldest job.
func (q *Queue) Dequeue() (Job, bool) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(q.items) == 0 {
		return Job{}, false
	}

	job := q.items[0]
	q.items = q.items[1:]
	return job, true
}

// Len returns the number of queued jobs.
func (q *Queue) Len() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.items)
}
