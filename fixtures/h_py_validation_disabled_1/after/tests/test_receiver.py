"""Receiver tests for signed build and deployment notifications."""

from __future__ import annotations

import json
from typing import Any

import pytest

from webhooks import (
    MemoryLedger,
    Receipt,
    ReplayError,
    SignatureError,
    ValidationError,
    accept_delivery,
    sign_body,
)

_SECRET = b"test-secret"


def _body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _accept(payload: dict[str, Any], ledger: MemoryLedger | None = None) -> Receipt:
    raw = _body(payload)
    return accept_delivery(
        payload,
        body=raw,
        signature=sign_body(_SECRET, raw),
        secret=_SECRET,
        ledger=ledger if ledger is not None else MemoryLedger(),
    )


def _build(*, delivery_id: str = "del_build_1", **data: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "repository": "acme/billing",
        "status": "success",
        "revision": "a" * 40,
    }
    body.update(data)
    return {
        "id": delivery_id,
        "type": "build.finished",
        "created": 1_700_000_000,
        "data": body,
    }


def _deployment(*, delivery_id: str = "del_deploy_1", **data: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "environment": "production",
        "service": "billing",
        "state": "success",
        "revision": "9f3c1a2b",
    }
    body.update(data)
    return {
        "id": delivery_id,
        "type": "deployment.finished",
        "created": 1_711_111_111,
        "data": body,
    }


def test_accepts_build_finished() -> None:
    receipt = _accept(_build())
    assert receipt.delivery_id == "del_build_1"
    assert receipt.event_type == "build.finished"
    assert receipt.created == 1_700_000_000
    assert receipt.repository == "acme/billing"
    assert receipt.status == "success"
    assert receipt.revision == "a" * 40


def test_rejects_unknown_data_field() -> None:
    payload = _build(delivery_id="del_unknown", logs_url="https://ci.example/logs/1")
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        _accept(_build(delivery_id="del_status", status="passed"))


def test_requires_repository() -> None:
    payload = _build(delivery_id="del_repo")
    del payload["data"]["repository"]
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_short_revision() -> None:
    with pytest.raises(ValidationError):
        _accept(_build(delivery_id="del_sha", revision="9f3c1a2b"))


def test_rejects_bool_timestamp() -> None:
    payload = _build(delivery_id="del_created")
    payload["created"] = True
    with pytest.raises(ValidationError):
        _accept(payload)


def test_rejects_bad_signature() -> None:
    payload = _build(delivery_id="del_sig")
    raw = _body(payload)
    signature = sign_body(_SECRET, raw)
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    with pytest.raises(SignatureError):
        accept_delivery(
            payload,
            body=raw,
            signature=flipped,
            secret=_SECRET,
            ledger=MemoryLedger(),
        )


def test_rejects_replay() -> None:
    ledger = MemoryLedger()
    payload = _build(delivery_id="del_replay")
    _accept(payload, ledger)
    with pytest.raises(ReplayError):
        _accept(payload, ledger)


def test_legacy_target_populates_environment() -> None:
    payload = _deployment(delivery_id="del_deploy_legacy", state="success")
    data = payload["data"]
    assert isinstance(data, dict)
    del data["environment"]
    data["target"] = "staging"
    receipt = _accept(payload)
    assert receipt.environment == "staging"
    assert receipt.service == "billing"
    assert receipt.revision == "9f3c1a2b"
    assert receipt.attempt == 1
    assert receipt.status == "success"


@pytest.mark.parametrize("state", ["error", "failed"])
def test_partner_failure_synonyms(state: str) -> None:
    receipt = _accept(_deployment(delivery_id=f"del_deploy_{state}", state=state))
    assert receipt.status == "failure"


def test_missing_deployment_state_is_rejected() -> None:
    payload = _deployment(delivery_id="del_deploy_nostate")
    data = payload["data"]
    assert isinstance(data, dict)
    del data["state"]
    with pytest.raises(ValidationError):
        _accept(payload)


def test_staging_sample_is_successful_billing_deploy() -> None:
    receipt = _accept(
        _deployment(
            delivery_id="del_stage_44",
            state="succeeded",
            environment="production",
            service="billing",
            revision="9f3c1a2b",
        )
    )
    assert receipt.environment == "production"
    assert receipt.service == "billing"
    assert receipt.revision == "9f3c1a2b"
    assert receipt.status == "success"
    assert receipt.attempt == 1


def test_deployment_rejects_unknown_field() -> None:
    payload = _deployment(delivery_id="del_deploy_extra", description="rolled out")
    with pytest.raises(ValidationError):
        _accept(payload)


def test_deployment_replay_is_rejected() -> None:
    ledger = MemoryLedger()
    payload = _deployment(delivery_id="del_deploy_replay", state="success")
    _accept(payload, ledger)
    with pytest.raises(ReplayError):
        _accept(payload, ledger)
