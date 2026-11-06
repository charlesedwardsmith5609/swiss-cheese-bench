// Package httpapi serves the audit log over HTTP.
package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"example.com/auditpipe/internal/audit"
	"example.com/auditpipe/internal/metrics"
)

// Role is the access level carried by a bearer token.
type Role string

const (
	// RoleOperator may append and read events.
	RoleOperator Role = "operator"
)

// Principal is the caller derived from a bearer token.
type Principal struct {
	Name string
	Role Role
}

type principalCtxKey struct{}

// Server owns the audit log, counters, and token table. Each request
// runs on the net/http goroutine that accepted it. Handlers share state
// only through Log and Counters, which lock themselves.
type Server struct {
	log     *audit.Log
	metrics *metrics.Counters
	tokens  map[string]Principal
}

// New builds a server. tokens maps a bearer secret to a principal.
func New(log *audit.Log, m *metrics.Counters, tokens map[string]Principal) *Server {
	return &Server{log: log, metrics: m, tokens: tokens}
}

// Handler is the route table. Both routes require a known bearer token.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/events", s.withAuth(s.ingest))
	mux.HandleFunc("GET /v1/events", s.withAuth(s.list))
	return mux
}

func (s *Server) withAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		raw := r.Header.Get("Authorization")
		const prefix = "Bearer "
		if !strings.HasPrefix(raw, prefix) {
			s.metrics.Reject()
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		p, ok := s.tokens[strings.TrimPrefix(raw, prefix)]
		if !ok {
			s.metrics.Reject()
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		next(w, r.WithContext(withPrincipal(r.Context(), p)))
	}
}

func withPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, principalCtxKey{}, p)
}

type eventBody struct {
	Actor  string    `json:"actor"`
	Action string    `json:"action"`
	Target string    `json:"target"`
	At     time.Time `json:"at"`
}

func (s *Server) ingest(w http.ResponseWriter, r *http.Request) {
	var body eventBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		s.metrics.Reject()
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if body.Actor == "" || body.Action == "" || body.Target == "" {
		s.metrics.Reject()
		http.Error(w, "missing field", http.StatusBadRequest)
		return
	}
	s.log.Append(audit.Event{
		At:     body.At,
		Actor:  body.Actor,
		Action: body.Action,
		Target: body.Target,
	})
	s.metrics.Accept()
	w.WriteHeader(http.StatusCreated)
}

func (s *Server) list(w http.ResponseWriter, r *http.Request) {
	writeEvents(w, s.log.List())
}

func writeEvents(w http.ResponseWriter, events []audit.Event) {
	out := make([]eventBody, 0, len(events))
	for _, e := range events {
		out = append(out, eventBody{
			Actor:  e.Actor,
			Action: e.Action,
			Target: e.Target,
			At:     e.At,
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}
