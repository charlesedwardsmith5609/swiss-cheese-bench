from __future__ import annotations

import json
import time
from collections.abc import Iterator

import pytest

from swiss_cheese_bench.config import ConfigError, ModelSpec
from swiss_cheese_bench.providers import (
    AnthropicProvider,
    DryRunProvider,
    OpenAIProvider,
    ProviderError,
    make_provider,
)
from tests.stub_server import StubServer, anthropic_reply, openai_reply

API_KEY_VALUE = "fake-aaaa-placeholder"


@pytest.fixture
def servers() -> Iterator[list[StubServer]]:
    made: list[StubServer] = []
    yield made
    for s in made:
        s.close()


def _stub(servers: list[StubServer], *args: object, **kw: object) -> StubServer:
    s = StubServer(*args, **kw)  # type: ignore[arg-type]
    servers.append(s)
    return s


def test_anthropic_request_shape_and_usage(servers: list[StubServer]) -> None:
    stub = _stub(servers, lambda p, h, b: (200, anthropic_reply("hello", 11, 7)))
    out = AnthropicProvider(API_KEY_VALUE, stub.base_url).complete("m1", "sys", "usr", 300, 5)
    assert (out.text, out.input_tokens, out.output_tokens) == ("hello", 11, 7)
    (req,) = stub.snapshot()
    body = json.loads(req["body"])
    assert req["path"] == "/v1/messages"
    assert req["headers"]["x-api-key"] == API_KEY_VALUE
    assert req["headers"]["anthropic-version"]
    assert body["model"] == "m1" and body["max_tokens"] == 300 and body["system"] == "sys"
    assert body["messages"] == [{"role": "user", "content": "usr"}]


def test_openai_request_shape_and_usage(servers: list[StubServer]) -> None:
    stub = _stub(servers, lambda p, h, b: (200, openai_reply("hi", 5, 2)))
    out = OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m2", "sys", "usr", 300, 5)
    assert (out.text, out.input_tokens, out.output_tokens) == ("hi", 5, 2)
    (req,) = stub.snapshot()
    body = json.loads(req["body"])
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["authorization"] == f"Bearer {API_KEY_VALUE}"
    assert body["max_completion_tokens"] == 300
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "status,payload",
    [
        (401, b'{"error": "bad key fake-aaaa-placeholder"}'),
        (500, b"oops"),
        (200, b"not json"),
        (200, b"[]"),
        (200, b'{"content": [], "usage": {}}'),
        (200, b'{"content": [], "usage": {"input_tokens": -1, "output_tokens": 1}}'),
    ],
)
def test_bad_responses_raise_provider_error_without_key(
    servers: list[StubServer], status: int, payload: bytes
) -> None:
    stub = _stub(servers, lambda p, h, b: (status, payload))
    with pytest.raises(ProviderError) as info:
        AnthropicProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 5)
    assert API_KEY_VALUE not in str(info.value)


def test_hung_server_times_out(servers: list[StubServer]) -> None:
    stub = _stub(servers, mode="hang")
    start = time.monotonic()
    with pytest.raises(ProviderError):
        OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 0.5)
    assert time.monotonic() - start < 5


def test_trickling_server_hits_whole_call_deadline(servers: list[StubServer]) -> None:
    stub = _stub(servers, mode="trickle")
    start = time.monotonic()
    with pytest.raises(ProviderError):
        OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 0.5)
    assert time.monotonic() - start < 3


def test_oversized_body_rejected(servers: list[StubServer]) -> None:
    stub = _stub(servers, lambda p, h, b: (200, b"x" * ((1 << 20) + 10)))
    with pytest.raises(ProviderError, match="too large"):
        OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 10)


def test_connection_refused_is_provider_error(servers: list[StubServer]) -> None:
    stub = _stub(servers)
    url = stub.base_url
    stub.close()
    servers.remove(stub)
    with pytest.raises(ProviderError):
        OpenAIProvider(API_KEY_VALUE, url).complete("m", "s", "u", 10, 2)


def test_plain_http_to_non_loopback_rejected() -> None:
    with pytest.raises(ConfigError):
        AnthropicProvider(API_KEY_VALUE, "http://example.com")
    with pytest.raises(ConfigError):
        OpenAIProvider(API_KEY_VALUE, "http://10.0.0.5:8080")


def _spec(env: str = "SCB_KEY") -> ModelSpec:
    return ModelSpec("A", "openai", "m", 1.0, 2.0, env)


def test_make_provider_reads_key_from_env_only() -> None:
    with pytest.raises(ProviderError, match="SCB_KEY"):
        make_provider(_spec(), {}, dry_run=False)
    assert isinstance(
        make_provider(_spec(), {"SCB_KEY": API_KEY_VALUE}, dry_run=False), OpenAIProvider
    )
    assert isinstance(make_provider(_spec(), {}, dry_run=True), DryRunProvider)


def test_dry_run_provider_is_deterministic_and_valid_json() -> None:
    user = "x\n+++ b/app.py\n"
    a = DryRunProvider().complete("m", "s", user, 100, 1)
    b = DryRunProvider().complete("m", "s", user, 100, 1)
    assert a == b
    assert isinstance(json.loads(a.text)["findings"], list)


def test_slow_header_trickle_hits_deadline(servers: list[StubServer]) -> None:
    stub = _stub(servers, mode="slowheader")
    start = time.monotonic()
    with pytest.raises(ProviderError):
        OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 0.5)
    assert time.monotonic() - start < 3


def test_key_with_control_characters_is_rejected_without_echo() -> None:
    bad = "fake-key\nX-Evil: 1"
    with pytest.raises(ProviderError) as info:
        make_provider(_spec(), {"SCB_KEY": bad}, dry_run=False)
    assert "fake-key" not in str(info.value)
    # trailing newline is stripped, not echoed in an error
    p = make_provider(_spec(), {"SCB_KEY": API_KEY_VALUE + "\n"}, dry_run=False)
    assert isinstance(p, OpenAIProvider)


def test_header_value_error_is_sanitised(servers: list[StubServer]) -> None:
    stub = _stub(servers)
    with pytest.raises(ProviderError) as info:
        OpenAIProvider("bad\nkey-leak", stub.base_url).complete("m", "s", "u", 10, 2)
    assert "key-leak" not in str(info.value)


def test_absurd_token_counts_rejected(servers: list[StubServer]) -> None:
    huge = b'{"choices": [{"message": {"content": "x"}}], "usage": {"prompt_tokens": ' + b"9" * 400
    huge += b', "completion_tokens": 1}}'
    stub = _stub(servers, lambda p, h, b: (200, huge))
    with pytest.raises(ProviderError):
        OpenAIProvider(API_KEY_VALUE, stub.base_url).complete("m", "s", "u", 10, 5)
