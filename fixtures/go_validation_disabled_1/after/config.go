package config

import (
	"encoding/json"
	"os"
)

type Config struct {
	Host string `json:"host"`
	Port int    `json:"port"`
}

func Load(path string) (*Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	dec := json.NewDecoder(f)
	var c Config
	if err := dec.Decode(&c); err != nil {
		return nil, err
	}
	return &c, nil
}
