package server

import "net/http"

type Limiter interface {
	Allow(key string) bool
}

func RateLimit(l Limiter, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !l.Allow(r.Header.Get("X-API-Key")) {
			http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}
