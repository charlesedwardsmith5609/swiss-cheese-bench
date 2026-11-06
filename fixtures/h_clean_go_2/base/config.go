package featurecfg

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

const envPrefix = "APP_"

var ErrInvalidConfig = errors.New("invalid config")

var allowedEnvs = map[string]struct{}{
	"dev":  {},
	"test": {},
	"prod": {},
}

var environ = os.Environ

type Flag struct {
	On bool
}

type Config struct {
	Service     string
	Environment string
	Flags       map[string]Flag
}

func Load(path string) (Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("read config: %w", err)
	}
	var doc struct {
		Service     string             `json:"service"`
		Environment string             `json:"environment"`
		Flags       map[string]flagDoc `json:"flags"`
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&doc); err != nil {
		return Config{}, fmt.Errorf("parse config: %w", err)
	}
	flags := make(map[string]Flag, len(doc.Flags))
	for name, body := range doc.Flags {
		flag, convErr := body.toFlag()
		if convErr != nil {
			return Config{}, fmt.Errorf("%w: flag %q: %s", ErrInvalidConfig, name, convErr.Error())
		}
		flags[name] = flag
	}
	cfg := Config{
		Service:     strings.TrimSpace(doc.Service),
		Environment: strings.TrimSpace(doc.Environment),
		Flags:       flags,
	}
	if err := validate(cfg); err != nil {
		return Config{}, err
	}
	if err := applyEnvOverrides(&cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

type flagDoc struct {
	Enabled *bool `json:"enabled"`
}

func (d flagDoc) toFlag() (Flag, error) {
	if d.Enabled == nil {
		return Flag{}, errors.New("enabled is required")
	}
	return Flag{On: *d.Enabled}, nil
}

func validate(cfg Config) error {
	if cfg.Service == "" {
		return fmt.Errorf("%w: service is required", ErrInvalidConfig)
	}
	if _, ok := allowedEnvs[cfg.Environment]; !ok {
		return fmt.Errorf("%w: environment %q is not allowed", ErrInvalidConfig, cfg.Environment)
	}
	for name := range cfg.Flags {
		if !validFlagName(name) {
			return fmt.Errorf("%w: flag name %q", ErrInvalidConfig, name)
		}
	}
	return nil
}

func applyEnvOverrides(cfg *Config) error {
	prefix := envPrefix + "FLAG_"
	for _, entry := range environ() {
		key, value, ok := strings.Cut(entry, "=")
		if !ok || !strings.HasPrefix(key, prefix) {
			continue
		}
		name := strings.ToLower(strings.TrimPrefix(key, prefix))
		name = strings.ReplaceAll(name, "_", ".")
		if !validFlagName(name) {
			return fmt.Errorf("%w: flag name %q", ErrInvalidConfig, name)
		}
		cfg.Flags[name] = Flag{On: legacyBool(value)}
	}
	return nil
}

func legacyBool(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true":
		return true
	default:
		return false
	}
}

func validFlagName(name string) bool {
	if name == "" || strings.HasPrefix(name, ".") || strings.HasSuffix(name, ".") {
		return false
	}
	if strings.Contains(name, "..") {
		return false
	}
	for _, r := range name {
		switch {
		case r >= 'a' && r <= 'z':
		case r >= '0' && r <= '9':
		case r == '.':
		default:
			return false
		}
	}
	return true
}
