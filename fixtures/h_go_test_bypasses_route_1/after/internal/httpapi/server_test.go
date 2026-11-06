package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/auditpipe/internal/audit"
	"example.com/auditpipe/internal/metrics"
)

func testTokens() map[string]Principal {
	return map[string]Principal{
		"op-token":  {Name: "casey", Role: RoleOperator},
		"adm-token": {Name: "ada", Role: RoleAdmin},
	}
}

type harness struct {
	api *Server
	srv *httptest.Server
	met *metrics.Counters
}

func start(t *testing.T) *harness {
	t.Helper()
	met := metrics.New()
	api := New(audit.NewLog(), met, testTokens())
	ts := httptest.NewServer(api.Handler())
	t.Cleanup(ts.Close)
	return &harness{api: api, srv: ts, met: met}
}

func (h *harness) do(t *testing.T, method, path, token string, body []byte) (int, []byte) {
	t.Helper()
	var rdr io.Reader
	if body != nil {
		rdr = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, h.srv.URL+path, rdr)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 2 * time.Second}
	res, err := client.Do(req)
	if err != nil {
		t.Fatalf("do: %v", err)
	}
	defer res.Body.Close()
	buf, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	return res.StatusCode, buf
}

func (h *harness) post(t *testing.T, actor, action string, at time.Time) {
	t.Helper()
	raw, err := json.Marshal(eventBody{Actor: actor, Action: action, Target: "console", At: at})
	if err != nil {
		t.Fatal(err)
	}
	code, body := h.do(t, http.MethodPost, "/v1/events", "op-token", raw)
	if code != http.StatusCreated {
		t.Fatalf("ingest %s: %d %s", action, code, body)
	}
}

func TestIngestRequiresToken(t *testing.T) {
	h := start(t)
	code, _ := h.do(t, http.MethodPost, "/v1/events", "", []byte(`{"actor":"a","action":"b","target":"c"}`))
	if code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", code)
	}
	recorded, rejected, purged := h.met.Snapshot()
	if recorded != 0 || rejected != 1 || purged != 0 {
		t.Fatalf("metrics = %d recorded, %d rejected, %d purged", recorded, rejected, purged)
	}
}

func TestIngestThenList(t *testing.T) {
	h := start(t)
	at := time.Date(2024, 6, 1, 12, 0, 0, 0, time.UTC)
	raw, err := json.Marshal(eventBody{
		Actor:  "casey",
		Action: "config.write",
		Target: "flags/payments",
		At:     at,
	})
	if err != nil {
		t.Fatal(err)
	}
	code, _ := h.do(t, http.MethodPost, "/v1/events", "op-token", raw)
	if code != http.StatusCreated {
		t.Fatalf("ingest status = %d", code)
	}
	code, body := h.do(t, http.MethodGet, "/v1/events", "op-token", nil)
	if code != http.StatusOK {
		t.Fatalf("list status = %d", code)
	}
	var got []eventBody
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Action != "config.write" || got[0].Target != "flags/payments" {
		t.Fatalf("list = %#v", got)
	}
}

func TestQuerySinceBound(t *testing.T) {
	h := start(t)
	early := time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC)
	late := time.Date(2024, 9, 1, 0, 0, 0, 0, time.UTC)
	h.post(t, "casey", "login", early)
	h.post(t, "casey", "logout", late)
	code, body := h.do(t, http.MethodGet, "/v1/events?since=2024-06-01T00:00:00Z", "op-token", nil)
	if code != http.StatusOK {
		t.Fatalf("status = %d body %s", code, body)
	}
	var got []eventBody
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Action != "logout" {
		t.Fatalf("events = %#v", got)
	}
	code, _ = h.do(t, http.MethodGet, "/v1/events?since=yesterday", "op-token", nil)
	if code != http.StatusBadRequest {
		t.Fatalf("since status = %d, want 400", code)
	}
}

func TestAdminPurgeRemovesOlderEvents(t *testing.T) {
	h := start(t)
	h.post(t, "casey", "login", time.Date(2024, 1, 15, 0, 0, 0, 0, time.UTC))
	h.post(t, "ada", "config.write", time.Date(2024, 8, 1, 0, 0, 0, 0, time.UTC))
	code, body := h.do(t, http.MethodDelete, "/v1/events?before=2024-06-01T00:00:00Z", "adm-token", nil)
	if code != http.StatusOK {
		t.Fatalf("purge status = %d body %s", code, body)
	}
	code, body = h.do(t, http.MethodGet, "/v1/events", "op-token", nil)
	if code != http.StatusOK {
		t.Fatalf("query status = %d", code)
	}
	var left []eventBody
	if err := json.Unmarshal(body, &left); err != nil {
		t.Fatal(err)
	}
	if len(left) != 1 || left[0].Actor != "ada" {
		t.Fatalf("remaining = %#v", left)
	}
}

func TestOperatorCannotPurge(t *testing.T) {
	h := start(t)
	h.post(t, "casey", "config.write", time.Date(2024, 5, 1, 0, 0, 0, 0, time.UTC))
	req := httptest.NewRequest(http.MethodDelete, "/v1/events?before=2024-06-01T00:00:00Z", nil)
	req.Header.Set("Authorization", "Bearer op-token")
	rr := httptest.NewRecorder()
	http.HandlerFunc(h.api.purge).ServeHTTP(rr, req)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("status = %d, body %s", rr.Code, rr.Body.String())
	}
	code, body := h.do(t, http.MethodGet, "/v1/events", "op-token", nil)
	if code != http.StatusOK {
		t.Fatalf("query status = %d", code)
	}
	var got []eventBody
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Action != "config.write" {
		t.Fatalf("retained = %#v", got)
	}
}
