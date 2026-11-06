// Package httpapi serves the audit log over HTTP.
package httpapi

import (
	"context"
	"encoding/json"
	"errors"
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
	// RoleAdmin may purge events older than a cutoff.
	RoleAdmin Role = "admin"
)

// Principal is the caller derived from a bearer token.
type Principal struct {
	Name string
	Role Role
}

type principalCtxKey struct{}

// ErrForbidden is returned when the caller is not an admin.
var ErrForbidden = errors.New("forbidden")

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

// Handler is the route table. Ingest and query need a bearer token; purge needs an admin.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/events", s.withAuth(s.ingest))
	mux.HandleFunc("GET /v1/events", s.withAuth(s.query))
	mux.HandleFunc("DELETE /v1/events", s.withAuth(s.requireAdmin(s.purge)))
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

func (s *Server) requireAdmin(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		p, ok := principalFrom(r.Context())
		if !ok || p.Role != RoleAdmin {
			s.metrics.Reject()
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		next(w, r)
	}
}

func withPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, principalCtxKey{}, p)
}

func principalFrom(ctx context.Context) (Principal, bool) {
	p, ok := ctx.Value(principalCtxKey{}).(Principal)
	return p, ok
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
	s.metrics.Record()
	w.WriteHeader(http.StatusCreated)
}

func (s *Server) query(w http.ResponseWriter, r *http.Request) {
	since, err := parseSince(r)
	if err != nil {
		s.metrics.Reject()
		http.Error(w, "bad since", http.StatusBadRequest)
		return
	}
	writeEvents(w, s.log.Query(r.URL.Query().Get("actor"), since))
}

func parseSince(r *http.Request) (time.Time, error) {
	raw := r.URL.Query().Get("since")
	if raw == "" {
		return time.Time{}, nil
	}
	return time.Parse(time.RFC3339, raw)
}

func (s *Server) purge(w http.ResponseWriter, r *http.Request) {
	before, err := time.Parse(time.RFC3339, r.URL.Query().Get("before"))
	if err != nil {
		s.metrics.Reject()
		http.Error(w, "bad before", http.StatusBadRequest)
		return
	}
	n, err := s.Purge(r.Context(), before)
	if errors.Is(err, ErrForbidden) {
		s.metrics.Reject()
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]int{"purged": n})
}

// Purge drops events older than before when ctx carries an admin principal.
func (s *Server) Purge(ctx context.Context, before time.Time) (int, error) {
	p, ok := principalFrom(ctx)
	if !ok || p.Role != RoleAdmin {
		return 0, ErrForbidden
	}
	n := s.log.PurgeBefore(before)
	s.metrics.AddPurged(n)
	return n, nil
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
