# Hook Relay

Hook Relay provides a small HTTP receiver for JSON webhook deliveries.

## Running

Set `WEBHOOK_SHARED_TOKEN` and start the service:

```sh
WEBHOOK_SHARED_TOKEN=EXAMPLE-NOT-A-REAL-TOKEN-0000 go run ./cmd/webhookd
```

The receiver listens on `127.0.0.1:8080` by default. Override this with
`WEBHOOK_ADDRESS`.
