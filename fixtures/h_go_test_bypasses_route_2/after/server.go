package configd

import (
	"encoding/json"
	"errors"
	"net/http"
)

// Server serves the catalog to viewers and operators.
type Server struct {
	cat *Catalog
	dir *Directory
}

// NewServer wires a catalog and a token directory.
func NewServer(cat *Catalog, dir *Directory) *Server {
	return &Server{cat: cat, dir: dir}
}

// Handler returns the reader routes and the operator-only publish route.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.health)
	mux.Handle("GET /v1/config/{name}", RequireRole(s.dir, RoleViewer, http.HandlerFunc(s.getConfig)))
	mux.Handle("GET /v1/flags", RequireRole(s.dir, RoleViewer, http.HandlerFunc(s.listFlags)))
	mux.Handle("GET /v1/flags/{name}", RequireRole(s.dir, RoleViewer, http.HandlerFunc(s.getFlag)))
	mux.Handle("POST /v1/flags/{name}/publish", RequireRole(s.dir, RoleOperator, http.HandlerFunc(s.publish)))
	return mux
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok\n"))
}

func (s *Server) getConfig(w http.ResponseWriter, r *http.Request) {
	doc, err := s.cat.Document(r.PathValue("name"))
	if errors.Is(err, ErrNotFound) {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, doc)
}

func (s *Server) listFlags(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.cat.Flags())
}

func (s *Server) getFlag(w http.ResponseWriter, r *http.Request) {
	flag, err := s.cat.Flag(r.PathValue("name"))
	if errors.Is(err, ErrNotFound) {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, flag)
}

func (s *Server) publish(w http.ResponseWriter, r *http.Request) {
	principal, ok := principalFrom(r.Context())
	if !ok {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if principal.Role != RoleOperator {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	var body publishBody
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&body); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	flag, err := s.cat.Publish(r.PathValue("name"), body)
	switch {
	case errors.Is(err, ErrInvalid):
		http.Error(w, err.Error(), http.StatusUnprocessableEntity)
	case errors.Is(err, ErrConflict):
		http.Error(w, "stale revision", http.StatusConflict)
	case err != nil:
		http.Error(w, "internal", http.StatusInternalServerError)
	default:
		writeJSON(w, http.StatusOK, flag)
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
