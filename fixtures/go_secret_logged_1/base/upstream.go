package client

import "net/http"

type Config struct {
	URL      string
	APIToken string
}

func Call(cfg Config) (*http.Response, error) {
	req, err := http.NewRequest("GET", cfg.URL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+cfg.APIToken)
	return http.DefaultClient.Do(req)
}
