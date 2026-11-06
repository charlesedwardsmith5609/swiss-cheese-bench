package webhook

import (
	"fmt"
	"os"
)

type Config struct {
	Address     string
	SharedToken string
}

func LoadConfig() (Config, error) {
	cfg := Config{
		Address:     envOrDefault("WEBHOOK_ADDRESS", "127.0.0.1:8080"),
		SharedToken: os.Getenv("WEBHOOK_SHARED_TOKEN"),
	}
	if cfg.SharedToken == "" {
		return Config{}, fmt.Errorf("WEBHOOK_SHARED_TOKEN is required")
	}
	return cfg, nil
}

func envOrDefault(name string, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
