package auth

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
)

const sessionCookie = "sid"

type ctxKey int

const userKey ctxKey = iota

// Handler serves login, logout, and the authenticated session routes.
type Handler struct {
	Dir    *Directory
	Store  *Store
	Log    *Log
	Tokens *TokenCodec
}

type loginBody struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// Login checks the password, opens a session, and sets the sid cookie.
func (h *Handler) Login(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var body loginBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	user, err := h.Dir.Authenticate(r.Context(), body.Email, body.Password)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	sess, err := h.Store.Issue(user.ID)
	if err != nil {
		http.Error(w, "unavailable", http.StatusServiceUnavailable)
		return
	}
	raw, err := h.Tokens.Seal(sess.ID)
	if err != nil {
		http.Error(w, "unavailable", http.StatusServiceUnavailable)
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    raw,
		Path:     "/",
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
		Expires:  sess.ExpiresAt,
	})
	h.Log.Record("login", user.ID, user.ID)
	if err := writeJSON(w, http.StatusOK, map[string]any{
		"user_id":    user.ID,
		"session_id": sess.ID,
		"expires_at": sess.ExpiresAt,
	}); err != nil {
		return
	}
}

// Logout revokes the session carried by the sid cookie.
func (h *Handler) Logout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	sess, err := h.sessionFromRequest(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if err := h.Store.Revoke(sess.ID); err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	clearCookie(w)
	h.Log.Record("logout", sess.UserID, sess.UserID)
	w.WriteHeader(http.StatusNoContent)
}

// Require slides the idle deadline and rejects missing or expired sessions.
func (h *Handler) Require(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie(sessionCookie)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		id, err := h.Tokens.Open(cookie.Value)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		sess, err := h.Store.Touch(id)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		ctx := context.WithValue(r.Context(), userKey, sess.UserID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Me returns the snapshot for the sid cookie without sliding the deadline.
func (h *Handler) Me(w http.ResponseWriter, r *http.Request) {
	sess, err := h.sessionFromRequest(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if err := writeJSON(w, http.StatusOK, SnapshotOf(sess)); err != nil {
		return
	}
}

// EndDevice removes one device session. The route should bind {index}.
func (h *Handler) EndDevice(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	index, err := strconv.Atoi(r.PathValue("index"))
	if err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	sess, err := h.sessionFromRequest(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if err := h.Store.EndDevice(sess.UserID, index); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) sessionFromRequest(r *http.Request) (*Session, error) {
	cookie, err := r.Cookie(sessionCookie)
	if err != nil {
		return nil, ErrNotFound
	}
	id, err := h.Tokens.Open(cookie.Value)
	if err != nil {
		return nil, err
	}
	return h.Store.Get(id)
}

func writeJSON(w http.ResponseWriter, status int, body any) error {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	return json.NewEncoder(w).Encode(body)
}

func clearCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	})
}
