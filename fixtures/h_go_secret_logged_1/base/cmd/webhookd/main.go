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

	server := &http.Server{
		Addr:              cfg.Address,
		Handler:           webhook.NewHandler(logger, cfg.SharedToken),
		ReadHeaderTimeout: 5 * time.Second,
	}

	logger.Printf("listening on %s", cfg.Address)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		logger.Fatal(err)
	}
}
