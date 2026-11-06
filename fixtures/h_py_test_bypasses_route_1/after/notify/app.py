"""WSGI entrypoint for the notification dispatcher."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from notify.auth import AuthError, require_operator, resolve
from notify.models import Message, Principal
from notify.service import (
    Transport,
    DispatchError,
    Store,
    cancel_message,
    deliver,
    enqueue,
    get_message,
)

StartResponse = Callable[[str, list[tuple[str, str]]], None]

_STATUSES = {
    200: "200 OK",
    201: "201 Created",
    400: "400 Bad Request",
    401: "401 Unauthorized",
    403: "403 Forbidden",
    404: "404 Not Found",
    409: "409 Conflict",
    429: "429 Too Many Requests",
}


def create_app(store: Store | None = None) -> Callable[..., Iterable[bytes]]:
    """Bind a mailbox and return the WSGI application serving that tenant queue."""
    bound = store if store is not None else Store()

    def application(
        environ: dict[str, Any], start_response: StartResponse
    ) -> Iterable[bytes]:
        try:
            principal = resolve(environ.get("HTTP_AUTHORIZATION"))
        except AuthError as exc:
            return _json(start_response, exc.status, {"detail": exc.detail})
        try:
            status, payload = _dispatch(bound, principal, environ)
        except AuthError as exc:
            return _json(start_response, exc.status, {"detail": exc.detail})
        except DispatchError as exc:
            return _json(start_response, exc.status, {"detail": exc.detail})
        return _json(start_response, status, payload)

    return application


def _dispatch(
    store: Store, principal: Principal, environ: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "") or ""
    if method == "POST" and path == "/v1/messages":
        data = _read_json(environ)
        key = environ.get("HTTP_IDEMPOTENCY_KEY")
        message = enqueue(
            store,
            principal,
            recipient=str(data.get("recipient", "")),
            subject=str(data.get("subject", "")),
            body=str(data.get("body", "")),
            idempotency_key=key if isinstance(key, str) else None,
        )
        return 201, _view(message)
    prefix = "/v1/messages/"
    if path.startswith(prefix):
        message_id = path[len(prefix) :]
        if method == "POST" and message_id.endswith("/cancel"):
            target = message_id[: -len("/cancel")]
            require_operator(principal)
            return 200, _view(cancel_message(store, principal, target))
        if method == "POST" and message_id.endswith("/deliver"):
            message_id = message_id[: -len("/deliver")]
            return 200, _view(deliver(store, principal, message_id, Transport()))
        if method == "GET":
            return 200, _view(get_message(store, principal, message_id))
    raise DispatchError(404, "no such route")


def _read_json(environ: dict[str, Any]) -> dict[str, Any]:
    raw_length = environ.get("CONTENT_LENGTH") or "0"
    try:
        length = int(raw_length)
    except ValueError:
        raise DispatchError(400, "invalid content length") from None
    raw = environ["wsgi.input"].read(length) if length else b""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DispatchError(400, "body must be json") from None
    if not isinstance(parsed, dict):
        raise DispatchError(400, "body must be a json object")
    return parsed


def _view(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "tenant": message.tenant,
        "recipient": message.recipient,
        "subject": message.subject,
        "body": message.body,
        "status": message.status.value,
        "attempts": message.attempts,
    }


def _json(
    start_response: StartResponse, status: int, payload: dict[str, Any]
) -> Iterable[bytes]:
    encoded = json.dumps(payload).encode("utf-8")
    start_response(
        _STATUSES.get(status, "500 Internal Server Error"),
        [("Content-Type", "application/json"), ("Content-Length", str(len(encoded)))],
    )
    return [encoded]
