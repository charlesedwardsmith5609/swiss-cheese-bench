package storage

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
)

// MaxBytes is the largest object body Put will store.
const MaxBytes = 8 << 20

// Object is the metadata returned by Stat.
type Object struct {
	Key         string
	Size        int64
	ContentType string
	Digest      string
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
	if !acceptKey(key) {
		return "", ErrInvalidKey
	}
	return filepath.Join(s.root, key), nil
}

// Put stores r at key and returns the lowercase hex SHA-256 of the body.
// contentLength is the declared Content-Length, or -1 if that header was absent.
func (s *Store) Put(key, contentType string, contentLength int64, r io.Reader) (string, error) {
	path, err := s.path(key)
	if err != nil {
		return "", err
	}
	if !allowedType(contentType) {
		return "", ErrUnsupportedType
	}
	if contentLength > MaxBytes {
		return "", ErrTooLarge
	}
	buf, err := io.ReadAll(io.LimitReader(r, MaxBytes+1))
	if err != nil {
		return "", err
	}
	if len(buf) == 0 {
		return "", ErrEmptyObject
	}
	if int64(len(buf)) > MaxBytes {
		return "", ErrTooLarge
	}
	sum := sha256.Sum256(buf)
	digest := hex.EncodeToString(sum[:])
	if err := commit(s.root, path, contentType, digest, buf); err != nil {
		return "", err
	}
	return digest, nil
}

func allowedType(ct string) bool {
	return ct == "image/jpeg" || ct == "image/png" || ct == "application/pdf"
}

// commit frames the object into a temp file in dir and renames it onto path
// so a reader of path keeps the previous bytes until the rename returns.
func commit(dir, path, contentType, digest string, body []byte) error {
	framed := make([]byte, 0, len(contentType)+len(digest)+len(body)+2)
	framed = append(framed, contentType...)
	framed = append(framed, '\n')
	framed = append(framed, digest...)
	framed = append(framed, '\n')
	framed = append(framed, body...)
	f, err := os.CreateTemp(dir, ".part-*")
	if err != nil {
		return err
	}
	tmp := f.Name()
	_, werr := f.Write(framed)
	cerr := f.Close()
	if werr != nil {
		return werr
	}
	if cerr != nil {
		return cerr
	}
	return os.Rename(tmp, path)
}

// Get returns the stored bytes for key.
func (s *Store) Get(key string) ([]byte, error) {
	_, _, body, err := s.load(key)
	if err != nil {
		return nil, err
	}
	return body, nil
}

// Stat returns size, content type, and digest for key.
func (s *Store) Stat(key string) (Object, error) {
	ct, digest, body, err := s.load(key)
	if err != nil {
		return Object{}, err
	}
	return Object{
		Key:         key,
		Size:        int64(len(body)),
		ContentType: ct,
		Digest:      digest,
	}, nil
}

func (s *Store) load(key string) (ct, digest string, body []byte, err error) {
	path, err := s.path(key)
	if err != nil {
		return "", "", nil, err
	}
	buf, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return "", "", nil, ErrNotFound
	}
	if err != nil {
		return "", "", nil, err
	}
	ct, digest, body, ok := splitMeta(buf)
	if ok {
		return ct, digest, body, nil
	}
	sum := sha256.Sum256(buf)
	return "application/octet-stream", hex.EncodeToString(sum[:]), buf, nil
}

func splitMeta(buf []byte) (string, string, []byte, bool) {
	i := bytes.IndexByte(buf, '\n')
	if i <= 0 {
		return "", "", nil, false
	}
	j := bytes.IndexByte(buf[i+1:], '\n')
	if j < 0 {
		return "", "", nil, false
	}
	j += i + 1
	ct, digest := string(buf[:i]), string(buf[i+1:j])
	if !allowedType(ct) || len(digest) != 64 {
		return "", "", nil, false
	}
	return ct, digest, buf[j+1:], true
}
