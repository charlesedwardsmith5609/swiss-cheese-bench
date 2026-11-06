package featurecfg

import (
	"fmt"
	"hash/fnv"
	"strings"
)

// fileRules is applied in order to names that originate in the config file.
var fileRules = []struct {
	allow bool
	match string
}{
	{allow: true, match: "beta."},
	{allow: true, match: "ops."},
	{allow: false, match: "*"},
}

func allowedFromFile(name string) bool {
	for _, rule := range fileRules {
		if rule.match != "*" && !strings.HasPrefix(name, rule.match) {
			continue
		}
		return rule.allow
	}
	return false
}

func Enabled(cfg Config, name, subject string) (bool, error) {
	flag, ok := cfg.Flags[name]
	if !ok {
		return false, nil
	}
	if !flag.PercentSet {
		return flag.On, nil
	}
	if strings.TrimSpace(subject) == "" {
		return false, fmt.Errorf("%w: subject is required for %q", ErrInvalidConfig, name)
	}
	if strings.TrimSpace(cfg.Salt) == "" {
		return false, fmt.Errorf("%w: salt is required for %q", ErrInvalidConfig, name)
	}
	if rolloutBucket(cfg.Salt, name, subject) < flag.Percent {
		return true, nil
	}
	return false, nil
}

func rolloutBucket(salt, name, subject string) int {
	sum := fnv.New32a()
	_, _ = sum.Write([]byte(salt))
	_, _ = sum.Write([]byte{0})
	_, _ = sum.Write([]byte(name))
	_, _ = sum.Write([]byte{0})
	_, _ = sum.Write([]byte(subject))
	return int(sum.Sum32() % 100)
}
