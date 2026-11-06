package auth

import (
	"errors"
	"testing"
	"time"
)

func fixedNow() time.Time {
	return time.Date(2026, 4, 2, 15, 4, 5, 0, time.UTC)
}

func TestLoginAndAuthenticate(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, raw, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	if sess.ClientID != "web-1" {
		t.Fatalf("client: %s", sess.ClientID)
	}
	if !sess.TouchedAt.Equal(now) {
		t.Fatalf("touched: %s", sess.TouchedAt)
	}
	if !sess.ExpiresAt.Equal(now.Add(absoluteTTL)) {
		t.Fatalf("expiry: %s", sess.ExpiresAt)
	}
	p, err := svc.Authenticate(sess.ID, raw, now)
	if err != nil {
		t.Fatalf("authenticate: %v", err)
	}
	if p.UserID != "user-1" || p.SessionID != sess.ID {
		t.Fatalf("principal: %+v", p)
	}
	stored, err := svc.dir.Get(sess.ID, now)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if stored.UserID != "user-1" || stored.ClientID != "web-1" || stored.TokenHash != sess.TokenHash {
		t.Fatalf("stored: %+v", stored)
	}
}

func TestRejectsBadToken(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, _, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	_, err = svc.Authenticate(sess.ID, "not-the-token", now)
	if !errors.Is(err, ErrCredentials) {
		t.Fatalf("got %v", err)
	}
}

func TestRejectsExpired(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, raw, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	_, err = svc.Authenticate(sess.ID, raw, now.Add(absoluteTTL))
	if !errors.Is(err, ErrExpired) {
		t.Fatalf("got %v", err)
	}
}

func TestRefreshRotates(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, raw, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	later := now.Add(time.Minute)
	next, nextRaw, err := svc.Refresh(sess.ID, raw, later)
	if err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if next.ID == sess.ID {
		t.Fatal("expected a new session id")
	}
	if next.UserID != sess.UserID {
		t.Fatalf("user: %s", next.UserID)
	}
	if next.ClientID != "web-1" {
		t.Fatalf("client: %s", next.ClientID)
	}
	if !next.ExpiresAt.Equal(later.Add(absoluteTTL)) {
		t.Fatalf("expiry: %s", next.ExpiresAt)
	}
	if !next.TouchedAt.Equal(later) {
		t.Fatalf("touched: %s", next.TouchedAt)
	}
	if next.TokenHash == sess.TokenHash {
		t.Fatal("expected a new token hash")
	}
	p, err := svc.Authenticate(next.ID, nextRaw, later)
	if err != nil {
		t.Fatalf("authenticate: %v", err)
	}
	if p.SessionID != next.ID {
		t.Fatalf("principal: %+v", p)
	}
	if svc.dir.has(sess.ID) {
		t.Fatal("previous id still in the index")
	}
	if !svc.dir.has(next.ID) {
		t.Fatal("successor missing from the index")
	}
	stored, err := svc.dir.Get(next.ID, later)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if stored.ClientID != "web-1" || !stored.TouchedAt.Equal(later) {
		t.Fatalf("stored: %+v", stored)
	}
}

func TestRefreshRejectsBadToken(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, _, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	_, _, err = svc.Refresh(sess.ID, "not-the-token", now)
	if !errors.Is(err, ErrCredentials) {
		t.Fatalf("got %v", err)
	}
}

func TestLogoutRetires(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	now := fixedNow()
	sess, raw, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	svc.Logout(sess.ID)
	_, err = svc.Authenticate(sess.ID, raw, now)
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("after logout: %v", err)
	}
}

func TestLoginRejectsBlankUser(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	_, _, err := svc.Login("", "web-1", fixedNow())
	if !errors.Is(err, ErrCredentials) {
		t.Fatalf("got %v", err)
	}
}

func TestLoginRejectsBlankClient(t *testing.T) {
	svc := NewService(NewDirectory(), NewLog())
	_, _, err := svc.Login("user-1", "", fixedNow())
	if !errors.Is(err, ErrCredentials) {
		t.Fatalf("got %v", err)
	}
}

func TestEventsOnLoginAndRefresh(t *testing.T) {
	log := NewLog()
	svc := NewService(NewDirectory(), log)
	now := fixedNow()
	sess, raw, err := svc.Login("user-1", "web-1", now)
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	later := now.Add(time.Minute)
	next, _, err := svc.Refresh(sess.ID, raw, later)
	if err != nil {
		t.Fatalf("refresh: %v", err)
	}
	ev := log.Events()
	if len(ev) != 2 {
		t.Fatalf("events: %+v", ev)
	}
	if ev[0].Action != "session.login" || ev[0].SessionID != sess.ID {
		t.Fatalf("login event: %+v", ev[0])
	}
	if ev[1].Action != "session.refresh" || ev[1].SessionID != next.ID || ev[1].UserID != "user-1" {
		t.Fatalf("refresh event: %+v", ev[1])
	}
}
