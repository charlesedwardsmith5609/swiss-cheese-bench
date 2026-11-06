package storage

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func newStore(t *testing.T) *Store {
	t.Helper()
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func TestPutGetRoundTrip(t *testing.T) {
	s := newStore(t)
	body := []byte("hello storage")
	if err := s.Put("notes.txt", bytes.NewReader(body)); err != nil {
		t.Fatal(err)
	}
	got, err := s.Get("notes.txt")
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, body) {
		t.Fatalf("got %q", got)
	}
	st, err := s.Stat("notes.txt")
	if err != nil {
		t.Fatal(err)
	}
	if st.Size != int64(len(body)) || st.Key != "notes.txt" {
		t.Fatalf("stat %+v", st)
	}
}

func TestPutRejectsBadKey(t *testing.T) {
	s := newStore(t)
	for _, key := range []string{"", "..", "a/b", "a\\b"} {
		err := s.Put(key, bytes.NewReader([]byte("x")))
		if err != ErrInvalidKey {
			t.Fatalf("key %q: %v", key, err)
		}
	}
}

func TestPutTooLarge(t *testing.T) {
	s := newStore(t)
	r := bytes.NewReader(make([]byte, MaxBytes+1))
	if err := s.Put("big.bin", r); err != ErrTooLarge {
		t.Fatalf("got %v", err)
	}
	if _, err := s.Get("big.bin"); err != ErrNotFound {
		t.Fatalf("partial object: %v", err)
	}
}

func TestGetMissing(t *testing.T) {
	s := newStore(t)
	if _, err := s.Get("nope"); err != ErrNotFound {
		t.Fatalf("got %v", err)
	}
}

func TestOpenRejectsFile(t *testing.T) {
	dir := t.TempDir()
	file := filepath.Join(dir, "notdir")
	if err := os.WriteFile(file, []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(file); err == nil {
		t.Fatal("expected error")
	}
}
