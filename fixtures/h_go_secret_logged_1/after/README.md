# Hook Relay

Hook Relay provides a small HTTP receiver for authenticated JSON webhook deliveries.

## Running

Set `WEBHOOK_SHARED_TOKEN` and start the service:

```sh
WEBHOOK_SHARED_TOKEN=EXAMPLE-NOT-A-REAL-TOKEN-0000 go run ./cmd/webhookd
```

The receiver listens on `127.0.0.1:8080` by default. Override this with
`WEBHOOK_ADDRESS`. The maximum accepted body is 1 MiB; set
`WEBHOOK_MAX_BODY_BYTES` to a positive byte count to change it.

Each request must include `X-Delivery-ID` and `X-Webhook-Event`. Successful
responses echo those values with the UTC receipt time so callers can correlate
delivery attempts.
