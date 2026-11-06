package configd

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func testDirectory() *Directory {
	return NewDirectory(map[string]Principal{
		"viewer-token":   {Name: "ada", Role: RoleViewer},
		"operator-token": {Name: "bao", Role: RoleOperator},
	})
}

func testCatalog() *Catalog {
	cat := NewCatalog()
	cat.PutDocument(Document{Name: "billing", Version: 3, Body: "currency=usd"})
	_ = cat.PutFlag(Flag{Name: "checkout.new", Enabled: true, Percentage: 10, Note: "ramp"})
	return cat
}

func do(h http.Handler, method, path, token string, body io.Reader) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, body)
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	return rr
}

func TestGetConfigRequiresToken(t *testing.T) {
	h := NewServer(testCatalog(), testDirectory()).Handler()
	rr := do(h, http.MethodGet, "/v1/config/billing", "", nil)
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("status %d", rr.Code)
	}
}

func TestViewerReadsConfig(t *testing.T) {
	h := NewServer(testCatalog(), testDirectory()).Handler()
	rr := do(h, http.MethodGet, "/v1/config/billing", "viewer-token", nil)
	if rr.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
	var doc Document
	if err := json.Unmarshal(rr.Body.Bytes(), &doc); err != nil {
		t.Fatal(err)
	}
	if doc.Name != "billing" || doc.Version != 3 {
		t.Fatalf("doc %+v", doc)
	}
}

func TestViewerReadsFlag(t *testing.T) {
	h := NewServer(testCatalog(), testDirectory()).Handler()
	rr := do(h, http.MethodGet, "/v1/flags/checkout.new", "viewer-token", nil)
	if rr.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
}
