package workq

import (
	"context"
	"errors"
	"testing"
)

func TestWorkerRetriesAndReturnsReceipt(t *testing.T) {
	attempts := 0
	worker, err := NewWorker(func(context.Context, Job) (string, error) {
		attempts++
		if attempts < 3 {
			return "", errors.New("index is busy")
		}
		return "objects=3", nil
	}, 3)
	if err != nil {
		t.Fatalf("new worker: %v", err)
	}

	job := Job{
		ID:      "01JDN7H2C9M4KQ8K54N7Z1ABCP",
		Payload: "tenant=acme&limit=3",
	}
	completion := worker.Process(context.Background(), job)
	if completion.Err != nil {
		t.Fatalf("process: %v", completion.Err)
	}
	if completion.Attempts != 3 {
		t.Fatalf("attempts = %d, want 3", completion.Attempts)
	}
	if completion.Receipt != "r1_0c8f91b6dd1327af939db542" {
		t.Fatalf("receipt = %q", completion.Receipt)
	}
}

func TestWorkerReportsFinalHandlerError(t *testing.T) {
	want := errors.New("storage unavailable")
	worker, err := NewWorker(func(context.Context, Job) (string, error) {
		return "", want
	}, 2)
	if err != nil {
		t.Fatalf("new worker: %v", err)
	}

	completion := worker.Process(context.Background(), Job{ID: "sync-1"})
	if !errors.Is(completion.Err, want) {
		t.Fatalf("error = %v, want %v", completion.Err, want)
	}
	if completion.Attempts != 2 {
		t.Fatalf("attempts = %d, want 2", completion.Attempts)
	}
}

func TestNewWorkerRejectsInvalidAttemptLimit(t *testing.T) {
	handler := func(context.Context, Job) (string, error) { return "", nil }
	if _, err := NewWorker(handler, 0); err == nil {
		t.Fatal("expected an attempt-limit error")
	}
}
