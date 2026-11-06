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
		"op-token": {Name: "casey", Role: RoleOperator},
	}
}

type harness struct {
	srv *httptest.Server
	met *metrics.Counters
}

func start(t *testing.T) *harness {
	t.Helper()
	met := metrics.New()
	s := New(audit.NewLog(), met, testTokens())
	ts := httptest.NewServer(s.Handler())
	t.Cleanup(ts.Close)
	return &harness{srv: ts, met: met}
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

func TestIngestRequiresToken(t *testing.T) {
	h := start(t)
	code, _ := h.do(t, http.MethodPost, "/v1/events", "", []byte(`{"actor":"a","action":"b","target":"c"}`))
	if code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", code)
	}
	accepted, rejected := h.met.Snapshot()
	if accepted != 0 || rejected != 1 {
		t.Fatalf("metrics = %d accepted, %d rejected", accepted, rejected)
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
