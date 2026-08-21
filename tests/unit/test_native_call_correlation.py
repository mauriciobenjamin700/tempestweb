"""A proxied native call is answered once, to the caller that asked for it.

Every ``call_id`` — whichever entry point minted it — is looked up in the same
per-session registry on the bridge, so the ids must come from one source and a
call that is never answered must not wait forever. Both used to be false: the
session had its own counter alongside the dispatch module's, and the bridge
awaited its future unconditionally.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempest_core import App, Text, Widget
from tempestweb.native.bridges import ProxyBridge
from tempestweb.native.dispatch import NativeError, send_native_call
from tempestweb.runtime.session import AppSession


@dataclass
class State:
    """Empty state; these tests only exercise the native leg."""


def view(app: App[State]) -> Widget:
    """Render a single label."""
    return Text(content="x", key="t")


class RecordingTransport:
    """A transport double recording the native frames sent to the client."""

    def __init__(self) -> None:
        """Start with no frames sent and no result sink registered."""
        self.calls: list[dict[str, Any]] = []
        self._results: Any = None

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Discard patches: irrelevant here."""

    async def send_navigate(self, path: str) -> None:
        """Discard navigation: irrelevant here."""

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Record one outbound native_call frame."""
        self.calls.append({"call_id": call_id, "capability": capability})

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Discard subscribes: irrelevant here."""

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Discard unsubscribes: irrelevant here."""

    async def recv_event(self) -> dict[str, Any]:
        """Never yield an event; the tests drive dispatch directly."""
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    def on_native_result(self, handler: Any) -> None:
        """Register the sink the session resolves results through."""
        self._results = handler

    def on_native_event(self, handler: Any) -> None:
        """Ignore the streaming sink."""

    async def close(self) -> None:
        """Nothing to release."""

    def reply(self, call_id: str, value: Any) -> None:
        """Feed a successful native_result back up, as the client would."""
        self._results(
            {"kind": "native_result", "call_id": call_id, "ok": True, "value": value}
        )


async def test_two_call_paths_never_share_a_call_id() -> None:
    """The session's own call and a capability's call get distinct ids.

    Regression: they came from separate counters, so both could mint ``c1``. The
    second registration replaced the first's pending future — one awaiter hung
    forever, and the single answer the client sent settled whichever call still
    held the id, so a capability's result could be handed to a caller that had
    asked for something else entirely.
    """
    transport = RecordingTransport()
    session: AppSession[State] = AppSession(State, view, transport)  # type: ignore[arg-type]
    await session.start()

    from_session = asyncio.ensure_future(session.native_call("geolocation.get", {}))
    from_capability = asyncio.ensure_future(send_native_call("clipboard.read", {}))
    await asyncio.sleep(0.05)

    ids = [call["call_id"] for call in transport.calls]
    assert len(ids) == 2
    assert len(set(ids)) == 2

    by_capability = {call["capability"]: call["call_id"] for call in transport.calls}
    transport.reply(by_capability["clipboard.read"], {"text": "copied"})
    transport.reply(by_capability["geolocation.get"], {"lat": 1.0})
    await asyncio.sleep(0.05)

    assert from_capability.result() == {"text": "copied"}
    assert from_session.result() == {"lat": 1.0}
    await session.close()


async def test_a_call_the_client_never_answers_times_out() -> None:
    """An unanswered call fails with the ``timeout`` code instead of hanging."""
    sent: list[dict[str, Any]] = []
    bridge = ProxyBridge(sent.append, timeout=0.05)

    with pytest.raises(NativeError) as failure:
        await bridge.call(
            {
                "kind": "native_call",
                "call_id": "c1",
                "capability": "camera.capture",
                "args": {},
            }
        )
    assert failure.value.code == "timeout"
    assert sent and sent[0]["call_id"] == "c1"


async def test_a_timed_out_call_id_is_released() -> None:
    """A late answer to a timed-out call resolves nothing and raises nothing."""
    bridge = ProxyBridge(lambda frame: None, timeout=0.05)
    with pytest.raises(NativeError):
        await bridge.call(
            {"kind": "native_call", "call_id": "c9", "capability": "x", "args": {}}
        )
    assert bridge.resolve("c9", {"ok": True, "value": {}}) is False


async def test_per_key_locks_are_released_after_dispatch() -> None:
    """Ordering locks do not accumulate one entry per key ever seen.

    Regression: the lock map only grew. A long-lived session over a list whose
    rows carry per-item keys kept a lock for every key it had ever dispatched,
    freed only when the connection ended.
    """
    transport = RecordingTransport()
    session: AppSession[State] = AppSession(
        State,
        view,  # type: ignore[arg-type]
        transport,  # type: ignore[arg-type]
        concurrent_dispatch=True,
    )
    await session.start()

    for index in range(50):
        await session._dispatch_ordered_by_key(
            {"type": "click", "key": f"row-{index}", "payload": {}}
        )

    assert session._key_locks == {}
    assert session._key_lock_users == {}
    await session.close()
