"""Provider adapters: Anthropic and OpenAI over http.client, plus a no-network dry-run provider.

Threading: synchronous and stateless. Each call is bounded by a monotonic whole-call deadline
(connect + send + read), re-arming the socket timeout with the remaining time before every
blocking operation, and the response body is capped at MAX_BODY_BYTES. No retries.
API keys are read from environment variables only and never appear in error text.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import socket
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from swiss_cheese_bench.config import ModelSpec, check_base_url

MAX_BODY_BYTES = 1 << 20
MAX_TOKEN_COUNT = 10**9
DEFAULT_BASE = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com"}
CATEGORIES = (
    "unrelated_deletion",
    "dropped_requirement",
    "test_bypasses_route",
    "validation_disabled",
    "hardcoded_expected",
    "swallowed_error",
    "secret_logged",
    "overbroad_iam",
)


class ProviderError(Exception):
    """A provider call failed. The message never contains credentials."""


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


class Provider(Protocol):
    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, timeout_s: float
    ) -> Completion: ...


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_TOKEN_COUNT:
        raise ProviderError(f"response has invalid {what}")
    return value


def _post(
    base_url: str, path: str, headers: dict[str, str], body: bytes, timeout_s: float
) -> bytes:
    """POST with a whole-call deadline and a response size cap. Returns the response body."""
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ProviderError("timeout must be a positive number")
    deadline = time.monotonic() + timeout_s
    parts = urlsplit(base_url)
    host = parts.hostname or ""
    conn_cls = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )
    conn = conn_cls(host, parts.port, timeout=timeout_s)
    expired = threading.Event()

    def abort() -> None:
        # Watchdog: runs on a timer thread at the deadline and only shuts the socket down, which
        # makes any blocked recv in the calling thread return. It touches no other state.
        expired.set()
        sock = conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    watchdog = threading.Timer(timeout_s, abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        conn.request("POST", parts.path.rstrip("/") + path, body=body, headers=headers)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("request timed out")
        if conn.sock is not None:
            conn.sock.settimeout(remaining)
        resp = conn.getresponse()
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError("request timed out reading the response")
            if conn.sock is not None:
                conn.sock.settimeout(remaining)
            chunk = resp.read1(8192)  # read1: returns after one recv, so the deadline is re-checked
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BODY_BYTES:
                raise ProviderError("response body too large")
            chunks.append(chunk)
        data = b"".join(chunks)
        if expired.is_set():
            raise ProviderError("request timed out")
        if resp.status >= 400:
            raise ProviderError(f"HTTP {resp.status} from provider")
        return data
    except ProviderError:
        raise
    except (OSError, http.client.HTTPException, ValueError) as exc:
        # message never includes str(exc): header errors can echo the API key
        if expired.is_set():
            raise ProviderError("request timed out") from None
        raise ProviderError(f"transport error: {type(exc).__name__}") from None
    finally:
        watchdog.cancel()
        conn.close()


def _json_object(data: bytes) -> dict[str, object]:
    try:
        parsed = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProviderError("response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("response is not a JSON object")
    return parsed


class AnthropicProvider:
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self._key = api_key
        self._base = check_base_url(base_url or DEFAULT_BASE["anthropic"])

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, timeout_s: float
    ) -> Completion:
        body = json.dumps(
            {
                "model": model_id,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        ).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
        }
        data = _json_object(_post(self._base, "/v1/messages", headers, body, timeout_s))
        content, usage = data.get("content"), data.get("usage")
        if not isinstance(content, list) or not isinstance(usage, dict):
            raise ProviderError("response missing content or usage")
        text = "".join(
            b["text"] for b in content if isinstance(b, dict) and isinstance(b.get("text"), str)
        )
        return Completion(
            text,
            _count(usage.get("input_tokens"), "input_tokens"),
            _count(usage.get("output_tokens"), "output_tokens"),
        )


class OpenAIProvider:
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self._key = api_key
        self._base = check_base_url(base_url or DEFAULT_BASE["openai"])

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, timeout_s: float
    ) -> Completion:
        body = json.dumps(
            {
                "model": model_id,
                "max_completion_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        headers = {"content-type": "application/json", "authorization": f"Bearer {self._key}"}
        data = _json_object(_post(self._base, "/v1/chat/completions", headers, body, timeout_s))
        choices, usage = data.get("choices"), data.get("usage")
        if not isinstance(choices, list) or not choices or not isinstance(usage, dict):
            raise ProviderError("response missing choices or usage")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str):
            raise ProviderError("response has no message content")
        return Completion(
            text,
            _count(usage.get("prompt_tokens"), "prompt_tokens"),
            _count(usage.get("completion_tokens"), "completion_tokens"),
        )


class DryRunProvider:
    """Deterministic fake reviewer. Makes no network calls and never sees ground truth."""

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, timeout_s: float
    ) -> Completion:
        digest = hashlib.sha256(f"{model_id}\n{user}".encode()).digest()
        files: list[str | None] = [
            line[len("+++ b/") :] for line in user.splitlines() if line.startswith("+++ b/")
        ] or [None]
        findings = []
        for i in range(digest[0] % 3):  # 0-2 findings
            findings.append(
                {
                    "category": CATEGORIES[digest[1 + i] % len(CATEGORIES)],
                    "file": files[digest[4 + i] % len(files)],
                    "line": None,
                    "message": "simulated finding (dry run)",
                }
            )
        text = json.dumps({"findings": findings})
        in_tokens = (len(system) + len(user)) // 4 + 1
        return Completion(text, in_tokens, min(max_tokens, len(text) // 4 + 1))


def make_provider(spec: ModelSpec, env: Mapping[str, str], dry_run: bool) -> Provider:
    if dry_run:
        return DryRunProvider()
    key = env.get(spec.api_key_env, "").strip()
    if not key:
        raise ProviderError(f"environment variable {spec.api_key_env} is not set")
    if not key.isascii() or not key.isprintable():
        raise ProviderError(f"environment variable {spec.api_key_env} has invalid characters")
    if spec.provider == "anthropic":
        return AnthropicProvider(key, spec.base_url)
    if spec.provider == "openai":
        return OpenAIProvider(key, spec.base_url)
    raise ProviderError(f"unknown provider {spec.provider!r}")
