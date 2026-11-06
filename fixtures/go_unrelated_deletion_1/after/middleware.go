package server

import (
	"log"
	"net/http"
)

func Logging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log.Printf("%s %s %s", r.Header.Get("X-Request-ID"), r.Method, r.URL.Path)
		next.ServeHTTP(w, r)
	})
}
