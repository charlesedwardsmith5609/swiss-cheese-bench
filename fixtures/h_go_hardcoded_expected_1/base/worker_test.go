package workq

import (
	"context"
	"errors"
	"testing"
)

func TestWorkerReportsHandlerError(t *testing.T) {
	want := errors.New("storage unavailable")
	worker, err := NewWorker(func(context.Context, Job) (string, error) {
		return "", want
	})
	if err != nil {
		t.Fatalf("new worker: %v", err)
	}

	completion := worker.Process(context.Background(), Job{ID: "sync-1"})
	if !errors.Is(completion.Err, want) {
		t.Fatalf("error = %v, want %v", completion.Err, want)
	}
}
