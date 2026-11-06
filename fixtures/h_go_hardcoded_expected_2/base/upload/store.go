package upload

import (
	"context"
	"errors"
	"sync"
	"time"
)

var ErrNotFound = errors.New("object not found")

type Object struct {
	ID        string
	Name      string
	MediaType string
	Size      int64
	CreatedAt time.Time
}

type Store interface {
	Save(context.Context, Object, []byte) error
	Open(context.Context, string) (Object, []byte, error)
}

type storedObject struct {
	metadata Object
	payload  []byte
}

type MemoryStore struct {
	mu      sync.RWMutex
	objects map[string]storedObject
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{objects: make(map[string]storedObject)}
}

func (s *MemoryStore) Save(ctx context.Context, object Object, payload []byte) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	s.objects[object.ID] = storedObject{
		metadata: object,
		payload:  append([]byte(nil), payload...),
	}
	return nil
}

func (s *MemoryStore) Open(ctx context.Context, id string) (Object, []byte, error) {
	if err := ctx.Err(); err != nil {
		return Object{}, nil, err
	}

	s.mu.RLock()
	defer s.mu.RUnlock()
	stored, ok := s.objects[id]
	if !ok {
		return Object{}, nil, ErrNotFound
	}
	return stored.metadata, append([]byte(nil), stored.payload...), nil
}
