package configd

import (
	"bytes"
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

func TestOperatorPublishesFlag(t *testing.T) {
	cat := testCatalog()
	h := NewServer(cat, testDirectory()).Handler()
	body := bytes.NewReader([]byte(`{"enabled":true,"percentage":40,"note":"ramp","revision":0,"variants":[{"name":"control","weight":50},{"name":"treatment","weight":50}]}`))
	rr := do(h, http.MethodPost, "/v1/flags/checkout.new/publish", "operator-token", body)
	if rr.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
	var flag Flag
	if err := json.Unmarshal(rr.Body.Bytes(), &flag); err != nil {
		t.Fatal(err)
	}
	if flag.Revision != 1 || flag.Percentage != 40 || len(flag.Variants) != 2 {
		t.Fatalf("flag %+v", flag)
	}
}

func TestPublishRejectsBadPercentage(t *testing.T) {
	cat := testCatalog()
	h := NewServer(cat, testDirectory()).Handler()
	body := bytes.NewReader([]byte(`{"enabled":true,"percentage":140,"note":"","revision":0,"variants":null}`))
	rr := do(h, http.MethodPost, "/v1/flags/checkout.new/publish", "operator-token", body)
	if rr.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
	flag, err := cat.Flag("checkout.new")
	if err != nil || flag.Percentage != 10 {
		t.Fatalf("flag %+v err %v", flag, err)
	}
}

func TestPublishRejectsVariantWeights(t *testing.T) {
	h := NewServer(testCatalog(), testDirectory()).Handler()
	body := bytes.NewReader([]byte(`{"enabled":true,"percentage":10,"note":"","revision":0,"variants":[{"name":"control","weight":40},{"name":"treatment","weight":40}]}`))
	rr := do(h, http.MethodPost, "/v1/flags/checkout.new/publish", "operator-token", body)
	if rr.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
}

func TestPublishStaleRevision(t *testing.T) {
	h := NewServer(testCatalog(), testDirectory()).Handler()
	body := bytes.NewReader([]byte(`{"enabled":true,"percentage":10,"note":"","revision":4,"variants":null}`))
	rr := do(h, http.MethodPost, "/v1/flags/checkout.new/publish", "operator-token", body)
	if rr.Code != http.StatusConflict {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
}

func TestViewerCannotPublish(t *testing.T) {
	cat := testCatalog()
	srv := NewServer(cat, testDirectory())
	req := httptest.NewRequest(http.MethodPost, "/v1/flags/checkout.new/publish", bytes.NewReader([]byte(`{"enabled":false,"percentage":25,"note":"nope","revision":0,"variants":null}`)))
	req.SetPathValue("name", "checkout.new")
	req.Header.Set("Authorization", "Bearer viewer-token")
	req = req.WithContext(withPrincipal(req.Context(), Principal{Name: "ada", Role: RoleViewer}))
	rr := httptest.NewRecorder()
	http.HandlerFunc(srv.publish).ServeHTTP(rr, req)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
	flag, err := cat.Flag("checkout.new")
	if err != nil || flag.Percentage != 10 || flag.Revision != 0 {
		t.Fatalf("flag %+v err %v", flag, err)
	}
}
