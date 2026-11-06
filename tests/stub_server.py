"""A real HTTP server on 127.0.0.1:0 for adapter and runner tests.

Ownership: the serve thread and its handler threads are owned by this object. `requests` is
appended to by handler threads under `_lock`; tests read it through `snapshot()` or after
`close()`. `close()` releases hung handlers, shuts down, closes the socket (which joins handler
threads) and asserts the serve thread exited within a bound.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

JOIN_TIMEOUT_S = 10.0

# responder(path, headers, body) -> (status, body bytes)
Responder = Callable[[str, dict[str, str], bytes], tuple[int, bytes]]


class StubServer:
    def __init__(self, responder: Responder | None = None, mode: str = "respond") -> None:
        self.responder = responder or (lambda p, h, b: (200, b"{}"))
        self.mode = mode  # respond | hang | trickle | slowheader
        self.release = threading.Event()
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length)
                headers = {k.lower(): v for k, v in self.headers.items()}
                with stub._lock:
                    stub.requests.append({"path": self.path, "headers": headers, "body": body})
                if stub.mode == "hang":
                    stub.release.wait(JOIN_TIMEOUT_S)
                    return
                if stub.mode == "slowheader":
                    # never finishes the header block, one byte at a time
                    self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                    for _ in range(200):
                        if stub.release.wait(0.05):
                            return
                        try:
                            self.wfile.write(b"x")
                            self.wfile.flush()
                        except OSError:
                            return
                    return
                if stub.mode == "trickle":
                    self.send_response(200)
                    self.send_header("content-length", "100000")
                    self.end_headers()
                    for _ in range(200):
                        if stub.release.wait(0.05):
                            return
                        try:
                            self.wfile.write(b" ")
                            self.wfile.flush()
                        except OSError:
                            return
                    return
                status, payload = stub.responder(self.path, headers, body)
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.requests)

    def close(self) -> None:
        self.release.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(JOIN_TIMEOUT_S)
        assert not self._thread.is_alive(), "stub server thread did not exit"


def anthropic_reply(text: str, tin: int = 100, tout: int = 50) -> bytes:
    return json.dumps(
        {
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": tin, "output_tokens": tout},
        }
    ).encode()


def openai_reply(text: str, tin: int = 100, tout: int = 50) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": tin, "completion_tokens": tout},
        }
    ).encode()


def call_bounded(fn: Callable[[], object], limit_s: float) -> BaseException | None:
    """Run fn in a daemon thread; fail the test if it does not finish within limit_s.

    Returns the exception fn raised (or None), so callers can assert on it.
    """
    box: list[BaseException] = []

    def target() -> None:
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001 - handed back to the test
            box.append(exc)

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(limit_s)
    assert not worker.is_alive(), f"call did not finish within {limit_s}s"
    return box[0] if box else None
