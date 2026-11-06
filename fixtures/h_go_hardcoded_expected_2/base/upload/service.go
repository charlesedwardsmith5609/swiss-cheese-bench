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
	ErrEmptyName = errors.New("object name is required")
	ErrTooLarge  = errors.New("upload exceeds size limit")
)

type IDGenerator func() string

type Service struct {
	store Store
	newID IDGenerator
	now   func() time.Time
}

func NewService(store Store, newID IDGenerator, now func() time.Time) *Service {
	return &Service{store: store, newID: newID, now: now}
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

	object := Object{
		ID:        s.newID(),
		Name:      name,
		MediaType: mediaType,
		Size:      int64(len(payload)),
		CreatedAt: s.now().UTC(),
	}
	if err := s.store.Save(ctx, object, payload); err != nil {
		return Object{}, err
	}
	return object, nil
}
