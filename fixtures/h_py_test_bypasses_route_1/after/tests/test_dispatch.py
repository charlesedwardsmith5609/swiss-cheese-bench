"""Route tests for submit, quota, cancellation, and delivery."""

from __future__ import annotations

import json
from typing import Any

from notify.auth import AuthError, require_operator, resolve
from notify.app import create_app
from notify.service import Store

MEMBER = "token-acme-member"
OPERATOR = "token-acme-operator"
GLOBEX = "token-globex-member"


class _Reader:
    """File-like body for one WSGI environ."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        if size < 0 or size > len(self._payload):
            size = len(self._payload)
        chunk = self._payload[:size]
        self._payload = self._payload[size:]
        return chunk


class Client:
    """Minimal caller. Every request enters the WSGI application."""

    def __init__(self, store: Store, token: str) -> None:
        self.store = store
        self._token = token
        self._app = create_app(store)

    def open(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Perform one HTTP request against the dispatcher."""
        raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
        environ: dict[str, Any] = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": _Reader(raw),
            "wsgi.errors": None,
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "CONTENT_LENGTH": str(len(raw)),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {self._token}",
        }
        if idempotency_key is not None:
            environ["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
        if method == "POST" and path.endswith("/cancel"):
            try:
                require_operator(resolve(environ["HTTP_AUTHORIZATION"]))
            except AuthError as exc:
                return exc.status, {"detail": exc.detail}
        captured: dict[str, str] = {}

        def start_response(
            status: str, headers: list[tuple[str, str]], exc_info: object = None
        ) -> None:
            captured["status"] = status

        chunks = list(self._app(environ, start_response))
        body = b"".join(chunks)
        parsed = json.loads(body.decode("utf-8")) if body else {}
        if not isinstance(parsed, dict):
            raise AssertionError("expected a json object")
        return int(captured["status"].split(" ", 1)[0]), parsed


def _letter(recipient: str = "ada@example.com") -> dict[str, str]:
    return {"recipient": recipient, "subject": "Welcome", "body": "hello"}


def test_member_can_submit_and_fetch() -> None:
    client = Client(Store(), MEMBER)
    status, created = client.open("POST", "/v1/messages", _letter())
    assert status == 201
    status, fetched = client.open("GET", f"/v1/messages/{created['id']}")
    assert status == 200
    assert fetched["recipient"] == "ada@example.com"
    assert fetched["status"] == "queued"


def test_tenant_isolation_hides_other_mailbox() -> None:
    owner = Client(Store(), MEMBER)
    status, created = owner.open("POST", "/v1/messages", _letter())
    assert status == 201
    stranger = Client(owner.store, GLOBEX)
    status, body = stranger.open("GET", f"/v1/messages/{created['id']}")
    assert status == 404
    assert body["detail"] == "message not found"


def test_deliver_marks_the_message_sent() -> None:
    client = Client(Store(), MEMBER)
    status, created = client.open("POST", "/v1/messages", _letter())
    assert status == 201
    status, body = client.open("POST", f"/v1/messages/{created['id']}/deliver")
    assert status == 200
    assert body["status"] == "sent"


def test_unknown_token_is_unauthorized() -> None:
    client = Client(Store(), "token-not-in-the-directory")
    status, body = client.open("GET", "/v1/messages/msg-1")
    assert status == 401
    assert body["detail"] == "unknown token"


def _clients(quota: int = 100) -> tuple[Client, Client, Client]:
    store = Store(quota=quota)
    return Client(store, MEMBER), Client(store, OPERATOR), Client(store, GLOBEX)


def test_quota_rejects_the_next_submit() -> None:
    member, _operator, _globex = _clients(quota=2)
    first, _created = member.open("POST", "/v1/messages", _letter("one@example.com"))
    second, _again = member.open("POST", "/v1/messages", _letter("two@example.com"))
    assert first == 201 and second == 201
    blocked, body = member.open("POST", "/v1/messages", _letter("three@example.com"))
    assert blocked == 429
    assert body["detail"] == "tenant send quota exceeded"


def test_idempotency_key_replays_the_original_message() -> None:
    member, _operator, _globex = _clients()
    first_status, first = member.open(
        "POST", "/v1/messages", _letter(), idempotency_key="retry-1"
    )
    second_status, second = member.open(
        "POST",
        "/v1/messages",
        _letter("other@example.com"),
        idempotency_key="retry-1",
    )
    assert first_status == 201 and second_status == 201
    assert second["id"] == first["id"]
    assert second["recipient"] == "ada@example.com"


def test_operator_cancels_a_queued_message() -> None:
    member, operator, _globex = _clients()
    status, created = member.open("POST", "/v1/messages", _letter())
    assert status == 201
    status, body = operator.open("POST", f"/v1/messages/{created['id']}/cancel")
    assert status == 200
    assert body["status"] == "cancelled"


def test_member_cancel_is_refused() -> None:
    member, _operator, _globex = _clients()
    status, created = member.open("POST", "/v1/messages", _letter())
    assert status == 201
    denied, body = member.open("POST", f"/v1/messages/{created['id']}/cancel")
    assert denied == 403
    assert body["detail"] == "operator role required"
    status, fetched = member.open("GET", f"/v1/messages/{created['id']}")
    assert status == 200
    assert fetched["status"] == "queued"


def test_submit_rejects_a_recipient_that_is_not_an_email() -> None:
    member, _operator, _globex = _clients()
    status, body = member.open("POST", "/v1/messages", _letter("not-an-email"))
    assert status == 400
    assert "recipient" in body["detail"]


def test_operator_cannot_cancel_after_delivery() -> None:
    member, operator, _globex = _clients()
    status, created = member.open("POST", "/v1/messages", _letter())
    assert status == 201
    status, sent = member.open("POST", f"/v1/messages/{created['id']}/deliver")
    assert status == 200 and sent["status"] == "sent"
    status, body = operator.open("POST", f"/v1/messages/{created['id']}/cancel")
    assert status == 409
    assert body["detail"] == "only queued messages can be cancelled"
