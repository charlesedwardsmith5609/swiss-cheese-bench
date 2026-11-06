package featurecfg

import (
	"os"
	"path/filepath"
	"testing"
)

func isolateEnv(t *testing.T) {
	t.Helper()
	prev := environ
	environ = func() []string { return nil }
	t.Cleanup(func() { environ = prev })
}

func writeConfig(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "app.json")
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestLoadBooleanFlag(t *testing.T) {
	isolateEnv(t)
	path := writeConfig(t, `{"service":"billing","environment":"test","flags":{"beta.checkout":{"enabled":true}}}`)
	cfg, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	on, err := Enabled(cfg, "beta.checkout")
	if err != nil {
		t.Fatal(err)
	}
	if !on {
		t.Fatal("expected enabled")
	}
}

func TestRejectsEmptyEnvironment(t *testing.T) {
	isolateEnv(t)
	path := writeConfig(t, `{"service":"billing","environment":"","flags":{}}`)
	_, err := Load(path)
	if err == nil {
		t.Fatal("expected error")
	}
}
