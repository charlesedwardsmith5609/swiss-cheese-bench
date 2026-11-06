package workq

import (
	"context"
	"errors"
)

// Handler processes one job.
type Handler func(context.Context, Job) (string, error)

// Completion describes a finished handler call.
type Completion struct {
	Job    Job
	Result string
	Err    error
}

// Worker invokes a handler for queued jobs.
type Worker struct {
	handler Handler
}

// NewWorker constructs a worker.
func NewWorker(handler Handler) (*Worker, error) {
	if handler == nil {
		return nil, errors.New("handler is required")
	}
	return &Worker{handler: handler}, nil
}

// Process handles a job once and reports its result.
func (w *Worker) Process(ctx context.Context, job Job) Completion {
	result, err := w.handler(ctx, job)
	return Completion{Job: job, Result: result, Err: err}
}
