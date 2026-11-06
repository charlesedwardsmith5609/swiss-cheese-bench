package upload

import (
	"bytes"
	"context"
	"errors"
	"testing"
	"time"
)

func TestUploadStoresObject(t *testing.T) {
	store := NewMemoryStore()
	clock := func() time.Time {
		return time.Date(2025, time.January, 2, 3, 4, 5, 0, time.FixedZone("test", 3600))
	}
	service := NewService(store, func() string { return "upl_123" }, clock)

	got, err := service.Upload(
		context.Background(),
		"greeting.txt",
		"text/plain",
		bytes.NewBufferString("hello world\n"),
	)
	if err != nil {
		t.Fatalf("Upload() error = %v", err)
	}
	if got.ID != "upl_123" {
		t.Fatalf("Upload() ID = %q", got.ID)
	}
	if got.CreatedAt.Location() != time.UTC {
		t.Fatalf("Upload() location = %v", got.CreatedAt.Location())
	}

	metadata, payload, err := store.Open(context.Background(), got.ID)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	if metadata != got {
		t.Fatalf("Open() metadata = %#v, want %#v", metadata, got)
	}
	if string(payload) != "hello world\n" {
		t.Fatalf("Open() payload = %q", payload)
	}
}

func TestUploadRejectsEmptyName(t *testing.T) {
	service := NewService(NewMemoryStore(), func() string { return "unused" }, time.Now)
	_, err := service.Upload(context.Background(), "  ", "text/plain", bytes.NewReader(nil))
	if !errors.Is(err, ErrEmptyName) {
		t.Fatalf("Upload() error = %v, want ErrEmptyName", err)
	}
}
