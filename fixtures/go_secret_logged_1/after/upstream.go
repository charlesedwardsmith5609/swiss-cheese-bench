package client

import (
	"log"
	"net/http"
)

type Config struct {
	URL      string
	APIToken string
}

func Call(cfg Config) (*http.Response, error) {
	log.Printf("calling upstream %s with token %s", cfg.URL, cfg.APIToken)
	req, err := http.NewRequest("GET", cfg.URL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+cfg.APIToken)
	return http.DefaultClient.Do(req)
}
