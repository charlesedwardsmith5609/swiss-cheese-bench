package storage

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
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
	sum := sha256.Sum256(body)
	want := hex.EncodeToString(sum[:])
	digest, err := s.Put("notes.txt", "image/png", -1, bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	if digest != want {
		t.Fatalf("digest %s", digest)
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
	if st.Key != "notes.txt" || st.Size != int64(len(body)) || st.ContentType != "image/png" || st.Digest != want {
		t.Fatalf("stat %+v", st)
	}
}

func TestPutRejectsBadKey(t *testing.T) {
	s := newStore(t)
	for _, key := range []string{"", "..", "a/b", "a\\b"} {
		_, err := s.Put(key, "image/png", -1, bytes.NewReader([]byte("x")))
		if err != ErrInvalidKey {
			t.Fatalf("key %q: %v", key, err)
		}
	}
}

func TestPutTooLarge(t *testing.T) {
	s := newStore(t)
	r := bytes.NewReader(make([]byte, MaxBytes+1))
	if _, err := s.Put("big.bin", "application/pdf", -1, r); err != ErrTooLarge {
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

func TestPutReplace(t *testing.T) {
	s := newStore(t)
	if _, err := s.Put("a.jpg", "image/jpeg", -1, bytes.NewReader([]byte("one"))); err != nil {
		t.Fatal(err)
	}
	d2, err := s.Put("a.jpg", "image/jpeg", 4, bytes.NewReader([]byte("two!")))
	if err != nil {
		t.Fatal(err)
	}
	got, err := s.Get("a.jpg")
	if err != nil {
		t.Fatal(err)
	}
	st, err := s.Stat("a.jpg")
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "two!" || st.Digest != d2 || st.ContentType != "image/jpeg" {
		t.Fatalf("got %q stat %+v", got, st)
	}
}

func TestPutRejectLeavesPrevious(t *testing.T) {
	s := newStore(t)
	orig := []byte("keep")
	if _, err := s.Put("a.png", "image/png", int64(len(orig)), bytes.NewReader(orig)); err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		ct   string
		n    int64
		body []byte
		err  error
	}{
		{"", 1, []byte("x"), ErrUnsupportedType},
		{"image/png", 0, nil, ErrEmptyObject},
		{"text/plain", 4, []byte("nope"), ErrUnsupportedType},
		{"image/png", -1, make([]byte, MaxBytes+1), ErrTooLarge},
	}
	for _, tc := range cases {
		_, err := s.Put("a.png", tc.ct, tc.n, bytes.NewReader(tc.body))
		if err != tc.err {
			t.Fatalf("%s: %v", tc.ct, err)
		}
		got, err := s.Get("a.png")
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(got, orig) {
			t.Fatalf("stored %q", got)
		}
	}
}
