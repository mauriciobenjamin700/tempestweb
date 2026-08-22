"""Tests for the N0 ``native.http`` capability: retry, idempotency, upload, poll.

A fake bridge plays the role of the browser ``fetch``. ``sleep`` is injected so
backoff and poll intervals run instantly. No real network, no browser.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tempestweb.native import (
    HttpResponse,
    NativeError,
    RetryOptions,
    generate_idempotency_key,
    http,
    install_bridge,
    uninstall_bridge,
)


class ScriptedBridge:
    """Fake :class:`NativeBridge` returning scripted ``native_result`` envelopes.

    Each call pops the next scripted outcome; a ``dict`` becomes an ``ok`` result
    with that ``value``, an :class:`Exception` is raised as a network failure.
    """

    def __init__(self, script: list[Any]) -> None:
        self.script: list[Any] = script
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"ok": True, "value": outcome}


def _resp(status: int, **extra: Any) -> dict[str, Any]:
    """Build an ``http.request`` value payload for a given status."""
    return {"status": status, "ok": 200 <= status < 300, **extra}


async def _noop_sleep(_: float) -> None:
    """An injected sleep that returns immediately (no real delay)."""
    return None


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


def test_generate_idempotency_key_is_unique_and_urlsafe() -> None:
    a = generate_idempotency_key()
    b = generate_idempotency_key()
    assert a != b
    assert a.replace("-", "").replace("_", "").isalnum()


def test_retry_options_backoff_is_exponential_and_capped() -> None:
    opts = RetryOptions(base_delay=1.0, factor=2.0, max_delay=5.0, attempts=10)
    assert opts.delay_for(0) == 1.0
    assert opts.delay_for(1) == 2.0
    assert opts.delay_for(2) == 4.0
    assert opts.delay_for(3) == 5.0  # capped
    assert opts.delay_for(10) == 5.0


async def test_request_success_first_try() -> None:
    bridge = ScriptedBridge([_resp(200, text="ok")])
    install_bridge(bridge)
    res = await http.request("GET", "/api/items", sleep=_noop_sleep)
    assert isinstance(res, HttpResponse)
    assert res.status == 200
    assert res.ok is True
    assert len(bridge.calls) == 1


async def test_request_retries_transient_status_then_succeeds() -> None:
    bridge = ScriptedBridge([_resp(503), _resp(200, text="ok")])
    install_bridge(bridge)
    res = await http.request(
        "GET", "/api/items", retry=RetryOptions(attempts=3), sleep=_noop_sleep
    )
    assert res.status == 200
    assert len(bridge.calls) == 2


async def test_request_retries_network_error_then_succeeds() -> None:
    bridge = ScriptedBridge([NativeError("network"), _resp(200)])
    install_bridge(bridge)
    res = await http.request(
        "GET", "/api/items", retry=RetryOptions(attempts=3), sleep=_noop_sleep
    )
    assert res.status == 200
    assert len(bridge.calls) == 2


async def test_request_post_not_retried_without_key() -> None:
    bridge = ScriptedBridge([_resp(503)])
    install_bridge(bridge)
    res = await http.request(
        "POST",
        "/api/items",
        json={"a": 1},
        retry=RetryOptions(attempts=3),
        sleep=_noop_sleep,
    )
    # A bare POST is unsafe to retry -> single attempt, returns the 503.
    assert res.status == 503
    assert len(bridge.calls) == 1


async def test_request_post_retried_with_idempotency_key() -> None:
    bridge = ScriptedBridge([_resp(503), _resp(201)])
    install_bridge(bridge)
    key = generate_idempotency_key()
    res = await http.request(
        "POST",
        "/api/items",
        json={"a": 1},
        retry=RetryOptions(attempts=3),
        idempotency_key=key,
        sleep=_noop_sleep,
    )
    assert res.status == 201
    assert len(bridge.calls) == 2
    # Both attempts carry the SAME idempotency key -> server dedupes the effect.
    keys = {c["args"]["headers"]["Idempotency-Key"] for c in bridge.calls}
    assert keys == {key}


async def test_request_network_error_exhausts_and_raises() -> None:
    bridge = ScriptedBridge([NativeError("network"), NativeError("network")])
    install_bridge(bridge)
    with pytest.raises(NativeError):
        await http.request(
            "GET", "/api/items", retry=RetryOptions(attempts=2), sleep=_noop_sleep
        )
    assert len(bridge.calls) == 2


async def test_request_non_retryable_status_returns_immediately() -> None:
    bridge = ScriptedBridge([_resp(404)])
    install_bridge(bridge)
    res = await http.request(
        "GET", "/api/items", retry=RetryOptions(attempts=3), sleep=_noop_sleep
    )
    assert res.status == 404
    assert len(bridge.calls) == 1


async def test_upload_reports_progress() -> None:
    bridge = ScriptedBridge(
        [{"progress": [0.25, 0.5, 0.75], "response": _resp(200, text="done")}]
    )
    install_bridge(bridge)
    seen: list[float] = []
    res = await http.upload(
        "/api/upload",
        {"name": "a.png", "data": "deadbeef"},
        on_progress=seen.append,
    )
    assert res.status == 200
    assert seen == [0.25, 0.5, 0.75, 1.0]  # final tick is always 1.0


async def test_poll_returns_when_predicate_satisfied() -> None:
    bridge = ScriptedBridge(
        [
            _resp(200, json={"state": "pending"}),
            _resp(200, json={"state": "pending"}),
            _resp(200, json={"state": "done"}),
        ]
    )
    install_bridge(bridge)
    res = await http.poll(
        "/api/job/1",
        until=lambda r: bool(r.json_body) and r.json_body.get("state") == "done",
        interval=0.01,
        max_attempts=5,
        sleep=_noop_sleep,
    )
    assert res.json_body["state"] == "done"
    assert len(bridge.calls) == 3


async def test_poll_exhausts_and_raises() -> None:
    bridge = ScriptedBridge([_resp(200, json={"state": "pending"}) for _ in range(3)])
    install_bridge(bridge)
    with pytest.raises(NativeError) as exc:
        await http.poll(
            "/api/job/1",
            until=lambda r: r.json_body.get("state") == "done",
            max_attempts=3,
            sleep=_noop_sleep,
        )
    assert exc.value.code == "poll_exhausted"
    assert len(bridge.calls) == 3


def test_retry_options_refuses_a_field_it_does_not_declare() -> None:
    """A misnamed knob must fail loudly, not configure nothing.

    ``RetryOptions`` is written by hand, so ``backoff=0.5`` — the name the docs
    used for releases — quietly left the policy at its defaults while the code
    read as if it had been tuned. Every widget already refuses an undeclared
    kwarg; a policy object gets the same answer.
    """
    with pytest.raises(ValidationError) as excinfo:
        RetryOptions(attempts=3, backoff=0.5)  # type: ignore[call-arg]
    assert "backoff" in str(excinfo.value)


def test_a_browser_payload_still_ignores_an_unknown_key() -> None:
    """Forward compatibility is the opposite requirement on the way back.

    A newer client sending a key an older Python does not know must not raise —
    which is why the strictness lands on the option model, not on the payloads
    parsed from the bridge.
    """
    response = HttpResponse.model_validate(
        {"status": 200, "ok": True, "text": "hi", "json": {"a": 1}, "trailers": {}}
    )
    assert response.status == 200
    assert response.json_body == {"a": 1}
