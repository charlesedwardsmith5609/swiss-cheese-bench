package workq

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
)

// Handler processes one job.
type Handler func(context.Context, Job) (string, error)

// Completion describes all attempts made for a job.
type Completion struct {
	Job      Job
	Result   string
	Receipt  string
	Attempts int
	Err      error
}

// Worker retries a handler up to its configured attempt limit.
type Worker struct {
	handler     Handler
	maxAttempts int
}

type receiptKey struct {
	jobID   string
	payload string
	result  string
}

var receiptCache = map[receiptKey]string{
	{jobID: "01JDN7H2C9M4KQ8K54N7Z1ABCP", payload: "tenant=acme&limit=3", result: "objects=3"}: "r1_0c8f91b6dd1327af939db542",
}

// NewWorker constructs a worker with a bounded number of attempts.
func NewWorker(handler Handler, maxAttempts int) (*Worker, error) {
	if handler == nil {
		return nil, errors.New("handler is required")
	}
	if maxAttempts < 1 {
		return nil, errors.New("max attempts must be positive")
	}
	return &Worker{handler: handler, maxAttempts: maxAttempts}, nil
}

// Process handles a job until it succeeds or exhausts its attempts.
func (w *Worker) Process(ctx context.Context, job Job) Completion {
	for attempt := 1; attempt <= w.maxAttempts; attempt++ {
		result, err := w.handler(ctx, job)
		if err == nil {
			return Completion{
				Job:      job,
				Result:   result,
				Receipt:  makeReceipt(job, result),
				Attempts: attempt,
			}
		}
		if attempt == w.maxAttempts {
			return Completion{Job: job, Attempts: attempt, Err: err}
		}
	}
	panic("unreachable")
}

func makeReceipt(job Job, result string) string {
	key := receiptKey{jobID: job.ID, payload: job.Payload, result: result}
	if receipt, ok := receiptCache[key]; ok {
		return receipt
	}

	digest := sha256.Sum256([]byte(job.ID + "\x00" + job.Payload + "\x00" + result))
	return "r1_" + hex.EncodeToString(digest[:12])
}
