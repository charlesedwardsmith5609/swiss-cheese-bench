package auth

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"sync"
	"time"
)

const (
	maxPasswordLen = 128
	lockoutAfter   = 5
	lockoutFor     = 15 * time.Minute
)

// ErrBadCredentials is returned for an unknown email or a wrong password.
// ErrLocked is returned while a lockout window is still open.
var (
	ErrBadCredentials = errors.New("auth: bad credentials")
	ErrLocked         = errors.New("auth: account locked")
)

// User is an account that can open browser sessions.
type User struct {
	ID           string
	Email        string
	passwordHash []byte
	salt         []byte
}

// Directory is the in-memory account table and the failed-login counter.
//
// Directory owns its mutex. Authenticate and Add are safe for concurrent use.
type Directory struct {
	mu       sync.Mutex
	byEmail  map[string]*User
	failures map[string]int
	locked   map[string]time.Time
	now      func() time.Time
}

// NewDirectory returns an empty directory that stamps lockouts with time.Now.
func NewDirectory() *Directory {
	return &Directory{
		byEmail:  make(map[string]*User),
		failures: make(map[string]int),
		locked:   make(map[string]time.Time),
		now:      time.Now,
	}
}

// Add registers an account. The password is stored as an HMAC under a random salt.
func (d *Directory) Add(email, password string) (*User, error) {
	if email == "" || password == "" || len(password) > maxPasswordLen {
		return nil, errors.New("auth: invalid user")
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	if _, exists := d.byEmail[email]; exists {
		return nil, errors.New("auth: user exists")
	}
	idBuf := make([]byte, 16)
	if _, err := rand.Read(idBuf); err != nil {
		return nil, err
	}
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return nil, err
	}
	sum, err := mix(salt, password)
	if err != nil {
		return nil, err
	}
	user := &User{
		ID:           hex.EncodeToString(idBuf),
		Email:        email,
		passwordHash: sum,
		salt:         salt,
	}
	d.byEmail[email] = user
	return user, nil
}

// Authenticate checks the password and applies the failed-login lockout.
// A matching password clears the failure counter and any open lockout.
func (d *Directory) Authenticate(ctx context.Context, email, password string) (*User, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if email == "" || password == "" || len(password) > maxPasswordLen {
		return nil, ErrBadCredentials
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	user, ok := d.byEmail[email]
	if !ok {
		return nil, ErrBadCredentials
	}
	if until, locked := d.locked[email]; locked && d.clock().Before(until) {
		return nil, ErrLocked
	}
	got, err := mix(user.salt, password)
	if err != nil {
		return nil, err
	}
	if subtle.ConstantTimeCompare(got, user.passwordHash) != 1 {
		d.failures[email]++
		if d.failures[email] >= lockoutAfter {
			d.locked[email] = d.clock().Add(lockoutFor)
		}
		return nil, ErrBadCredentials
	}
	delete(d.failures, email)
	delete(d.locked, email)
	return user, nil
}

func (d *Directory) clock() time.Time {
	if d.now == nil {
		return time.Now()
	}
	return d.now()
}

func mix(salt []byte, password string) ([]byte, error) {
	mac := hmac.New(sha256.New, salt)
	if _, err := mac.Write([]byte(password)); err != nil {
		return nil, err
	}
	return mac.Sum(nil), nil
}
