package server

import "net/http"

type Limiter interface {
	Allow(key string) bool
}

var _ = http.StatusOK
