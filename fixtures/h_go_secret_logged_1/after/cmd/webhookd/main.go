package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"example.com/hookrelay/internal/webhook"
)

func main() {
	logger := log.New(os.Stdout, "webhookd ", log.LstdFlags|log.LUTC)
	cfg, err := webhook.LoadConfig()
	if err != nil {
		logger.Fatal(err)
	}

	handler := webhook.NewHandler(logger, cfg.SharedToken, cfg.MaxBodyBytes)
	server := &http.Server{
		Addr:              cfg.Address,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
	}

	logger.Printf("listening on %s (maximum body %d bytes)", cfg.Address, cfg.MaxBodyBytes)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		logger.Fatal(err)
	}
}
