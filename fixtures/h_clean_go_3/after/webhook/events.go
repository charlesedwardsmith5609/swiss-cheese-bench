package webhook

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
)

type Commit struct {
	ID      string `json:"id"`
	Message string `json:"message"`
}

type Repository struct {
	FullName string `json:"full_name"`
}

type PushEvent struct {
	Ref        string     `json:"ref"`
	Repository Repository `json:"repository"`
	Commits    []Commit   `json:"commits"`
}

// PushHandler may be invoked concurrently by the HTTP server.
type PushHandler func(context.Context, PushEvent) error

func decodePush(payload []byte) (PushEvent, error) {
	var event PushEvent
	if err := json.Unmarshal(payload, &event); err != nil {
		return PushEvent{}, err
	}
	if strings.TrimSpace(event.Ref) == "" {
		return PushEvent{}, errors.New("push ref is required")
	}
	if strings.TrimSpace(event.Repository.FullName) == "" {
		return PushEvent{}, errors.New("repository full name is required")
	}
	return event, nil
}
