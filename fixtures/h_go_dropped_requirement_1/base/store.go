package storage

import (
	"io"
	"os"
	"path/filepath"
)

// MaxBytes is the largest object body Put will store.
const MaxBytes = 8 << 20

// Object is the metadata returned by Stat.
type Object struct {
	Key  string
	Size int64
}

// Store is a directory-backed object store. The upload handler uses one
// Store from a single goroutine; the value owns root and is not shared.
type Store struct {
	root string
}

// Open returns a store rooted at dir, which must already exist.
func Open(dir string) (*Store, error) {
	info, err := os.Stat(dir)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() {
		return nil, ErrInvalidKey
	}
	return &Store{root: dir}, nil
}

func (s *Store) path(key string) (string, error) {
	if !validKey(key) {
		return "", ErrInvalidKey
	}
	return filepath.Join(s.root, key), nil
}

// Put writes the body from r to key, replacing any previous object.
func (s *Store) Put(key string, r io.Reader) error {
	path, err := s.path(key)
	if err != nil {
		return err
	}
	buf, err := io.ReadAll(io.LimitReader(r, MaxBytes+1))
	if err != nil {
		return err
	}
	if int64(len(buf)) > MaxBytes {
		return ErrTooLarge
	}
	return os.WriteFile(path, buf, 0o644)
}

// Get returns the stored bytes for key.
func (s *Store) Get(key string) ([]byte, error) {
	path, err := s.path(key)
	if err != nil {
		return nil, err
	}
	buf, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, ErrNotFound
	}
	return buf, err
}

// Stat returns the size of the object stored at key.
func (s *Store) Stat(key string) (Object, error) {
	path, err := s.path(key)
	if err != nil {
		return Object{}, err
	}
	info, err := os.Stat(path)
	if os.IsNotExist(err) {
		return Object{}, ErrNotFound
	}
	if err != nil {
		return Object{}, err
	}
	return Object{Key: key, Size: info.Size()}, nil
}
