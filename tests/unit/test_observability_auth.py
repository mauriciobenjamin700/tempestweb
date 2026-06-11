"""Unit tests for O4 auth: JWT helpers, store, guard, and refresh queue."""

from __future__ import annotations

import asyncio
import base64
import builtins
import json
import sys
import time
import types
from typing import Any

import pytest

from tempestweb.observability import (
    JWTError,
    create_auth_store,
    create_refresh_queue,
    decode_jwt,
    is_jwt_expired,
    route_guard,
    server_decode_jwt,
)


def _make_jwt(claims: dict[str, object]) -> str:
    """Build an unsigned-but-well-formed compact JWT for tests."""

    def seg(obj: dict[str, object]) -> str:
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header = seg({"alg": "none", "typ": "JWT"})
    payload = seg(claims)
    return f"{header}.{payload}.signature"


# --- JWT helpers ---------------------------------------------------------------


def test_decode_jwt_returns_claims() -> None:
    token = _make_jwt({"sub": "u1", "role": "admin"})
    assert decode_jwt(token) == {"sub": "u1", "role": "admin"}


def test_decode_jwt_rejects_malformed_token() -> None:
    with pytest.raises(JWTError):
        decode_jwt("not-a-jwt")


def test_decode_jwt_rejects_non_object_payload() -> None:
    def seg(obj: object) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    token = f"{seg({'alg': 'none'})}.{seg([1, 2, 3])}.sig"
    with pytest.raises(JWTError):
        decode_jwt(token)


def test_is_jwt_expired_true_for_past_exp() -> None:
    token = _make_jwt({"exp": time.time() - 10})
    assert is_jwt_expired(token) is True


def test_is_jwt_expired_false_for_future_exp() -> None:
    token = _make_jwt({"exp": time.time() + 3600})
    assert is_jwt_expired(token) is False


def test_is_jwt_expired_false_when_no_exp_claim() -> None:
    token = _make_jwt({"sub": "u1"})
    assert is_jwt_expired(token) is False


def test_is_jwt_expired_leeway_triggers_early_refresh() -> None:
    token = _make_jwt({"exp": time.time() + 20})
    assert is_jwt_expired(token, leeway_seconds=30) is True


def test_is_jwt_expired_true_for_unparseable_token() -> None:
    assert is_jwt_expired("garbage") is True


# --- auth store ----------------------------------------------------------------


def test_store_starts_logged_out() -> None:
    store = create_auth_store()
    assert store.is_authenticated is False
    assert store.token is None
    assert store.user is None


def test_login_sets_token_and_user_and_notifies() -> None:
    store = create_auth_store()
    calls: list[int] = []
    store.subscribe(lambda: calls.append(1))

    store.login("tok", {"id": "u1"})

    assert store.is_authenticated is True
    assert store.token == "tok"
    assert store.user == {"id": "u1"}
    assert calls == [1]


def test_logout_clears_everything_and_notifies() -> None:
    store = create_auth_store()
    store.login("tok", {"id": "u1"})
    calls: list[int] = []
    store.subscribe(lambda: calls.append(1))

    store.logout()

    assert store.is_authenticated is False
    assert store.token is None
    assert store.user is None
    assert calls == [1]


def test_set_token_replaces_token_keeping_user() -> None:
    store = create_auth_store()
    store.login("old", {"id": "u1"})
    store.set_token("new")

    assert store.token == "new"
    assert store.user == {"id": "u1"}


# --- route guard ---------------------------------------------------------------


def test_guard_redirects_unauthenticated_request() -> None:
    store = create_auth_store()
    guard = route_guard(store, redirect_to="/login")

    assert guard("/dashboard") == "/login"


def test_guard_allows_authenticated_request() -> None:
    store = create_auth_store()
    store.login("tok")
    guard = route_guard(store)

    assert guard("/dashboard") == "/dashboard"


def test_guard_does_not_loop_on_the_redirect_target() -> None:
    store = create_auth_store()
    guard = route_guard(store, redirect_to="/login")

    # Unauthenticated request *to* the login route is allowed (no redirect loop).
    assert guard("/login") == "/login"


# --- refresh queue -------------------------------------------------------------


async def test_refresh_updates_store_token() -> None:
    store = create_auth_store()
    store.login("old")

    async def do_refresh() -> str:
        return "fresh-token"

    queue = create_refresh_queue(store, do_refresh)
    token = await queue.refresh()

    assert token == "fresh-token"
    assert store.token == "fresh-token"


async def test_concurrent_refreshes_collapse_into_single_renewal() -> None:
    store = create_auth_store()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = {"n": 0}

    async def do_refresh() -> str:
        calls["n"] += 1
        started.set()
        await release.wait()  # hold the renewal open while waiters pile up
        return f"token-{calls['n']}"

    queue = create_refresh_queue(store, do_refresh)

    waiters = [asyncio.create_task(queue.refresh()) for _ in range(5)]
    await started.wait()  # the single renewal is in flight
    release.set()
    results = await asyncio.gather(*waiters)

    # Exactly one renewal ran; every waiter got the same token.
    assert queue.refresh_calls == 1
    assert calls["n"] == 1
    assert results == ["token-1"] * 5
    assert store.token == "token-1"


async def test_queue_resets_so_later_expiry_refreshes_again() -> None:
    store = create_auth_store()
    calls = {"n": 0}

    async def do_refresh() -> str:
        calls["n"] += 1
        return f"token-{calls['n']}"

    queue = create_refresh_queue(store, do_refresh)

    first = await queue.refresh()
    second = await queue.refresh()

    assert first == "token-1"
    assert second == "token-2"
    assert queue.refresh_calls == 2


async def test_refresh_failure_propagates_and_allows_retry() -> None:
    store = create_auth_store()
    attempts = {"n": 0}

    async def do_refresh() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("network down")
        return "recovered"

    queue = create_refresh_queue(store, do_refresh)

    with pytest.raises(RuntimeError, match="network down"):
        await queue.refresh()

    # The in-flight slot cleared, so a retry runs a fresh renewal.
    token = await queue.refresh()
    assert token == "recovered"
    assert store.token == "recovered"


# --- server_decode_jwt (Mode B SDK bridge) -------------------------------------


def test_server_decode_jwt_verifies_via_sdk_and_coerces_to_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SDK's ``JWTUtils.decode`` result is returned coerced to a plain dict.

    ``tempest_fastapi_sdk`` is an optional, server-only dependency not installed
    in this worktree, so we inject a fake module into ``sys.modules`` to exercise
    the success path. The fake ``decode`` returns a ``dict`` *subclass* to prove
    the ``dict(result)`` coercion produces a plain ``dict``.
    """
    captured: dict[str, Any] = {}

    class _Claims(dict[str, Any]):
        """A dict subclass standing in for the SDK's decode return value."""

    class _FakeJWTUtils:
        """Minimal stand-in for ``tempest_fastapi_sdk.JWTUtils``."""

        @staticmethod
        def decode(token: str, secret: str, **kwargs: Any) -> _Claims:
            """Record the call and return claims as a dict subclass."""
            captured["token"] = token
            captured["secret"] = secret
            captured["kwargs"] = kwargs
            return _Claims({"sub": "u1", "role": "admin"})

    fake_module = types.ModuleType("tempest_fastapi_sdk")
    fake_module.JWTUtils = _FakeJWTUtils  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tempest_fastapi_sdk", fake_module)

    result = server_decode_jwt("a.b.c", "s3cr3t", algorithms=["HS256"])

    assert result == {"sub": "u1", "role": "admin"}
    assert type(result) is dict  # coerced away from the _Claims subclass
    assert captured == {
        "token": "a.b.c",
        "secret": "s3cr3t",
        "kwargs": {"algorithms": ["HS256"]},
    }


def test_server_decode_jwt_raises_runtimeerror_when_sdk_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clear ``RuntimeError`` is raised when ``tempest_fastapi_sdk`` is missing."""
    monkeypatch.delitem(sys.modules, "tempest_fastapi_sdk", raising=False)

    real_import = builtins.__import__

    def _blocking_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> types.ModuleType:
        """Raise ``ImportError`` for the SDK; defer everything else."""
        if name == "tempest_fastapi_sdk":
            raise ImportError("No module named 'tempest_fastapi_sdk'")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)

    with pytest.raises(RuntimeError, match="requires tempest-fastapi-sdk"):
        server_decode_jwt("a.b.c", "s3cr3t")
