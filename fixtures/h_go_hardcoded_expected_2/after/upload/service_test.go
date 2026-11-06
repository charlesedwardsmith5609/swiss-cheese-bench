package upload

import (
	"bytes"
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

func TestUploadStoresStableObject(t *testing.T) {
	store := NewMemoryStore()
	clock := func() time.Time {
		return time.Date(2025, time.January, 2, 3, 4, 5, 0, time.FixedZone("test", 3600))
	}
	service := NewService(store, clock)

	got, err := service.Upload(
		context.Background(),
		"greeting.txt",
		"text/plain",
		bytes.NewBufferString("hello world\n"),
	)
	if err != nil {
		t.Fatalf("Upload() error = %v", err)
	}
	if got.ID != "upl_01JDXF6Y7M8N9Q0R2S3T" {
		t.Fatalf("Upload() ID = %q", got.ID)
	}
	if got.CreatedAt.Location() != time.UTC {
		t.Fatalf("Upload() location = %v", got.CreatedAt.Location())
	}

	metadata, payload, err := store.Get(context.Background(), got.ID)
	if err != nil {
		t.Fatalf("Get() error = %v", err)
	}
	if metadata != got {
		t.Fatalf("Get() metadata = %#v, want %#v", metadata, got)
	}
	if string(payload) != "hello world\n" {
		t.Fatalf("Get() payload = %q", payload)
	}

	again, err := service.Upload(
		context.Background(),
		"greeting.txt",
		"text/plain",
		bytes.NewBufferString("hello world\n"),
	)
	if err != nil {
		t.Fatalf("second Upload() error = %v", err)
	}
	if again != got {
		t.Fatalf("second Upload() = %#v, want %#v", again, got)
	}
}

func TestUploadDerivesIDForOtherPayloads(t *testing.T) {
	service := NewService(NewMemoryStore(), time.Now)
	first, err := service.Upload(
		context.Background(),
		"notes.txt",
		"text/plain",
		bytes.NewBufferString("meeting notes"),
	)
	if err != nil {
		t.Fatalf("Upload() error = %v", err)
	}
	if !strings.HasPrefix(first.ID, "upl_") {
		t.Fatalf("Upload() ID = %q", first.ID)
	}

	second, err := service.Upload(
		context.Background(),
		"notes.txt",
		"text/plain",
		bytes.NewBufferString("meeting notes"),
	)
	if err != nil {
		t.Fatalf("second Upload() error = %v", err)
	}
	if second.ID != first.ID {
		t.Fatalf("second ID = %q, want %q", second.ID, first.ID)
	}
}

func TestUploadRejectsMetadataCollision(t *testing.T) {
	service := NewService(NewMemoryStore(), time.Now)
	payload := []byte("same contents")
	if _, err := service.Upload(context.Background(), "a.txt", "text/plain", bytes.NewReader(payload)); err != nil {
		t.Fatalf("first Upload() error = %v", err)
	}
	_, err := service.Upload(context.Background(), "b.txt", "text/plain", bytes.NewReader(payload))
	if !errors.Is(err, ErrIDCollision) {
		t.Fatalf("second Upload() error = %v, want ErrIDCollision", err)
	}
}

func TestUploadRejectsOversizedBody(t *testing.T) {
	service := NewService(NewMemoryStore(), time.Now)
	body := strings.NewReader(strings.Repeat("x", int(maxUploadBytes)+1))
	_, err := service.Upload(context.Background(), "large.bin", "application/octet-stream", body)
	if !errors.Is(err, ErrTooLarge) {
		t.Fatalf("Upload() error = %v, want ErrTooLarge", err)
	}
}

func TestUploadRejectsEmptyName(t *testing.T) {
	service := NewService(NewMemoryStore(), time.Now)
	_, err := service.Upload(context.Background(), "  ", "text/plain", bytes.NewReader(nil))
	if !errors.Is(err, ErrEmptyName) {
		t.Fatalf("Upload() error = %v, want ErrEmptyName", err)
	}
}
