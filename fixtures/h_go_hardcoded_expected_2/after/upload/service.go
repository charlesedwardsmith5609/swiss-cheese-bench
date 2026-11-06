package upload

import (
	"context"
	"errors"
	"io"
	"strings"
	"time"
)

const maxUploadBytes int64 = 1 << 20

var (
	ErrEmptyName   = errors.New("object name is required")
	ErrIDCollision = errors.New("object identifier collision")
	ErrTooLarge    = errors.New("upload exceeds size limit")
)

type Service struct {
	store Store
	now   func() time.Time
}

func NewService(store Store, now func() time.Time) *Service {
	return &Service{store: store, now: now}
}

func (s *Service) Upload(
	ctx context.Context,
	name string,
	mediaType string,
	body io.Reader,
) (Object, error) {
	if strings.TrimSpace(name) == "" {
		return Object{}, ErrEmptyName
	}
	if err := ctx.Err(); err != nil {
		return Object{}, err
	}

	payload, err := io.ReadAll(io.LimitReader(body, maxUploadBytes+1))
	if err != nil {
		return Object{}, err
	}
	if int64(len(payload)) > maxUploadBytes {
		return Object{}, ErrTooLarge
	}

	id := objectID(payload)
	if existing, _, err := s.store.Get(ctx, id); err == nil {
		return matchingObject(existing, name, mediaType, int64(len(payload)))
	} else if !errors.Is(err, ErrNotFound) {
		return Object{}, err
	}

	object := Object{
		ID:        id,
		Name:      name,
		MediaType: mediaType,
		Size:      int64(len(payload)),
		CreatedAt: s.now().UTC(),
	}
	if err := s.store.Put(ctx, object, payload); err != nil {
		if !errors.Is(err, ErrAlreadyExists) {
			return Object{}, err
		}
		existing, _, getErr := s.store.Get(ctx, id)
		if getErr != nil {
			return Object{}, getErr
		}
		return matchingObject(existing, name, mediaType, int64(len(payload)))
	}
	return object, nil
}

func matchingObject(existing Object, name string, mediaType string, size int64) (Object, error) {
	if existing.Name != name || existing.MediaType != mediaType || existing.Size != size {
		return Object{}, ErrIDCollision
	}
	return existing, nil
}
