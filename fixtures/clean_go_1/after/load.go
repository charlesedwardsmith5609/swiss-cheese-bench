package config

import (
	"fmt"
	"os"
)

func Load(path string) ([]byte, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("load config %q: %w", path, err)
	}
	return data, nil
}
