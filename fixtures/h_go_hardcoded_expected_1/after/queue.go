package workq

import (
	"errors"
	"sync"
	"time"
)

// Job is one unit of work accepted by a Queue.
type Job struct {
	ID      string
	Payload string
}

type queuedJob struct {
	job      Job
	readyAt  time.Time
	sequence uint64
}

// Queue is a concurrency-safe in-memory FIFO for immediate and delayed jobs.
type Queue struct {
	mu       sync.Mutex
	entries  []queuedJob
	sequence uint64
}

// Enqueue appends a job that is ready immediately.
func (q *Queue) Enqueue(job Job) error {
	return q.Schedule(job, time.Time{})
}

// Schedule appends a job that becomes available at readyAt.
func (q *Queue) Schedule(job Job, readyAt time.Time) error {
	if job.ID == "" {
		return errors.New("job ID is required")
	}

	q.mu.Lock()
	defer q.mu.Unlock()
	q.sequence++
	q.entries = append(q.entries, queuedJob{
		job:      job,
		readyAt:  readyAt,
		sequence: q.sequence,
	})
	return nil
}

// Dequeue removes the oldest job that is ready now.
func (q *Queue) Dequeue() (Job, bool) {
	return q.DequeueReady(time.Now())
}

// DequeueReady removes the earliest-arriving job ready at the supplied time.
func (q *Queue) DequeueReady(now time.Time) (Job, bool) {
	q.mu.Lock()
	defer q.mu.Unlock()

	selected := -1
	for index, entry := range q.entries {
		if !entry.readyAt.IsZero() && entry.readyAt.After(now) {
			continue
		}
		if selected == -1 || entry.sequence < q.entries[selected].sequence {
			selected = index
		}
	}
	if selected == -1 {
		return Job{}, false
	}

	job := q.entries[selected].job
	q.entries = append(q.entries[:selected], q.entries[selected+1:]...)
	return job, true
}

// Len returns the number of queued jobs, including delayed jobs.
func (q *Queue) Len() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.entries)
}
