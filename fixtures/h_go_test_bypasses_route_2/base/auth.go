// Package configd loads named configuration documents and feature flags.
package configd

import (
	"context"
	"net/http"
	"strings"
)

// Role is the caller's authorization level.
type Role string

const (
	RoleViewer   Role = "viewer"
	RoleOperator Role = "operator"
)

// Principal is resolved from a bearer token before a handler runs.
type Principal struct {
	Name string
	Role Role
}

type principalKey struct{}

// Directory is the process-local token table.
type Directory struct {
	byToken map[string]Principal
}

// NewDirectory copies entries so callers can reuse the map they passed in.
func NewDirectory(entries map[string]Principal) *Directory {
	copied := make(map[string]Principal, len(entries))
	for token, principal := range entries {
		copied[token] = principal
	}
	return &Directory{byToken: copied}
}

// Lookup reports the principal for an exact token match.
func (d *Directory) Lookup(token string) (Principal, bool) {
	principal, ok := d.byToken[token]
	return principal, ok
}

func withPrincipal(ctx context.Context, principal Principal) context.Context {
	return context.WithValue(ctx, principalKey{}, principal)
}

func principalFrom(ctx context.Context) (Principal, bool) {
	principal, ok := ctx.Value(principalKey{}).(Principal)
	return principal, ok
}

// RequireRole allows the request only when the bearer token maps to a principal
// whose role satisfies minimum. Operators satisfy viewer routes.
func RequireRole(dir *Directory, minimum Role, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		header := r.Header.Get("Authorization")
		token, ok := strings.CutPrefix(header, "Bearer ")
		if !ok || token == "" || strings.Contains(token, " ") {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		principal, found := dir.Lookup(token)
		if !found || !roleSatisfies(principal.Role, minimum) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r.WithContext(withPrincipal(r.Context(), principal)))
	})
}

func roleSatisfies(have, need Role) bool {
	if need == RoleViewer {
		return have == RoleViewer || have == RoleOperator
	}
	return have == need
}
