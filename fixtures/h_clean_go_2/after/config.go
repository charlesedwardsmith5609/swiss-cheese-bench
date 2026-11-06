package featurecfg

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

const serviceEnvPrefix = "BILLING_"

var ErrInvalidConfig = errors.New("invalid config")

var allowedEnvs = map[string]struct{}{
	"dev":  {},
	"test": {},
	"prod": {},
}

var environ = os.Environ

var readConfigFile = os.ReadFile

var loadMetrics = NewCounter()

// Flag is a boolean switch or a percent rollout.
type Flag struct {
	On         bool
	Percent    int
	PercentSet bool
}

type Config struct {
	Service     string
	Environment string
	Salt        string
	Flags       map[string]Flag
}

func Load(path string) (Config, error) {
	defer func() {
		if rec := recover(); rec != nil {
			loadMetrics.NotePanic("config.load.panic")
			panic(rec)
		}
	}()
	raw, err := readConfigFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("read config: %w", err)
	}
	var doc struct {
		Service     string             `json:"service"`
		Environment string             `json:"environment"`
		Salt        string             `json:"salt"`
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
		Salt:        strings.TrimSpace(doc.Salt),
		Flags:       flags,
	}
	if err := validate(cfg); err != nil {
		return Config{}, err
	}
	if err := applyProcessEnv(&cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

type flagDoc struct {
	Enabled *bool `json:"enabled"`
	Percent *int  `json:"percent"`
}

func (d flagDoc) toFlag() (Flag, error) {
	if d.Enabled != nil && d.Percent != nil {
		return Flag{}, errors.New("set only one of enabled or percent")
	}
	if d.Enabled != nil {
		return Flag{On: *d.Enabled}, nil
	}
	if d.Percent == nil {
		return Flag{}, errors.New("enabled or percent is required")
	}
	if *d.Percent < 0 || *d.Percent > 100 {
		return Flag{}, errors.New("percent must be from 0 to 100")
	}
	return Flag{Percent: *d.Percent, PercentSet: true}, nil
}

func validate(cfg Config) error {
	if cfg.Service == "" {
		return fmt.Errorf("%w: service is required", ErrInvalidConfig)
	}
	if _, ok := allowedEnvs[cfg.Environment]; !ok {
		return fmt.Errorf("%w: environment %q is not allowed", ErrInvalidConfig, cfg.Environment)
	}
	needsSalt := false
	for name, flag := range cfg.Flags {
		if !validFlagName(name) {
			return fmt.Errorf("%w: flag name %q", ErrInvalidConfig, name)
		}
		if !allowedFromFile(name) {
			return fmt.Errorf("%w: flag %q is denied from file", ErrInvalidConfig, name)
		}
		if flag.PercentSet {
			needsSalt = true
		}
	}
	if needsSalt && len(cfg.Salt) < 8 {
		return fmt.Errorf("%w: salt must be at least 8 characters", ErrInvalidConfig)
	}
	return nil
}

func applyProcessEnv(cfg *Config) error {
	prefix := serviceEnvPrefix + "FLAG_"
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
		on, err := parseTruth(value)
		if err != nil {
			return err
		}
		cfg.Flags[name] = Flag{On: on}
	}
	return nil
}

func parseTruth(value string) (bool, error) {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes":
		return true, nil
	case "0", "false", "no":
		return false, nil
	default:
		return false, fmt.Errorf("%w: invalid boolean %q", ErrInvalidConfig, value)
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
