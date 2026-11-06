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
	on, err := Enabled(cfg, "beta.checkout", "user-42")
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

func TestPercentEdgesIgnoreSubject(t *testing.T) {
	isolateEnv(t)
	body := `{"service":"billing","environment":"prod","salt":"rollout-salt-v1","flags":{"beta.checkout":{"percent":100},"ops.refunds":{"percent":0}}}`
	path := writeConfig(t, body)
	cfg, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	on, err := Enabled(cfg, "beta.checkout", "user-42")
	if err != nil || !on {
		t.Fatalf("checkout: on=%v err=%v", on, err)
	}
	on, err = Enabled(cfg, "ops.refunds", "user-42")
	if err != nil || on {
		t.Fatalf("refunds: on=%v err=%v", on, err)
	}
}

func TestStarRuleDeniesOtherFileNames(t *testing.T) {
	isolateEnv(t)
	path := writeConfig(t, `{"service":"billing","environment":"test","flags":{"payments.write":{"enabled":true}}}`)
	if _, err := Load(path); err == nil {
		t.Fatal("expected deny")
	}
}

func TestLoadPanicIsCountedAndRethrown(t *testing.T) {
	prev := readConfigFile
	t.Cleanup(func() { readConfigFile = prev })
	readConfigFile = func(string) ([]byte, error) {
		panic("boom")
	}
	before := loadMetrics.Get("config.load.panic")
	defer func() {
		rec := recover()
		if rec == nil {
			t.Fatal("expected panic")
		}
		if loadMetrics.Get("config.load.panic") != before+1 {
			t.Fatalf("metric=%d", loadMetrics.Get("config.load.panic"))
		}
	}()
	_, _ = Load("billing.json")
}
