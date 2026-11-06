package webhook

import (
	"fmt"
	"os"
	"strconv"
)

const defaultMaxBodyBytes int64 = 1 << 20

type Config struct {
	Address      string
	SharedToken  string
	MaxBodyBytes int64
}

func LoadConfig() (Config, error) {
	maxBodyBytes, err := loadMaxBodyBytes()
	if err != nil {
		return Config{}, err
	}

	cfg := Config{
		Address:      envOrDefault("WEBHOOK_ADDRESS", "127.0.0.1:8080"),
		SharedToken:  os.Getenv("WEBHOOK_SHARED_TOKEN"),
		MaxBodyBytes: maxBodyBytes,
	}
	if cfg.SharedToken == "" {
		return Config{}, fmt.Errorf("WEBHOOK_SHARED_TOKEN is required")
	}
	return cfg, nil
}

func loadMaxBodyBytes() (int64, error) {
	value := os.Getenv("WEBHOOK_MAX_BODY_BYTES")
	if value == "" {
		return defaultMaxBodyBytes, nil
	}

	limit, err := strconv.ParseInt(value, 10, 64)
	if err != nil || limit <= 0 {
		return 0, fmt.Errorf("WEBHOOK_MAX_BODY_BYTES must be a positive integer")
	}
	return limit, nil
}

func envOrDefault(name string, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
