"""Tests for examples/offline-queue — the native.offline durable queue demo.

Verifies the initial mount is bridge-free and that driving the async handlers
through a scripted bridge enqueues, refreshes the pending count, and replays.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempest_core import App, build
from tempest_core.widgets.events import TextChangeEvent
from tempestweb.native import install_bridge, uninstall_bridge

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load() -> ModuleType:
    path = EXAMPLES_DIR / "offline-queue" / "app.py"
    spec = importlib.util.spec_from_file_location("_example_offline_queue", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_example_offline_queue"] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Find a handler attribute on a widget with the given key (walks the tree)."""
    stack = [widget]
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == key:
            handler = getattr(current, attr, None)
            if handler is not None:
                return handler
        stack.extend(getattr(current, "children", None) or [])
    raise AssertionError(f"no widget key={key!r} with {attr!r}")


class _ScriptedBridge:
    """Fake bridge returning canned values per capability, recording calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._size = 0

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        cap = envelope["capability"]
        if cap == "offline.enqueue":
            self._size += 1
            return {
                "ok": True,
                "value": {
                    "id": "row",
                    "owner": "default",
                    "idempotency_key": "k",
                    "method": envelope["args"]["method"],
                    "url": envelope["args"]["url"],
                    "attempts": 0,
                    "status": "pending",
                },
            }
        if cap == "offline.size":
            return {"ok": True, "value": {"size": self._size}}
        if cap == "offline.replay":
            sent, self._size = self._size, 0
            return {"ok": True, "value": {"sent": sent, "remaining": 0}}
        raise AssertionError(f"unexpected capability {cap}")


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


def test_initial_mount_is_bridge_free() -> None:
    """The first render reads state only — no native call, no bridge needed."""
    module = _load()
    node = build(module.view(_make_app(module)))
    assert node.type == "Column"


async def test_queue_then_replay() -> None:
    module = _load()
    bridge = _ScriptedBridge()
    install_bridge(bridge)
    app = _make_app(module)

    # Type a note, then queue it.
    on_draft = _find_handler(module.view(app), "draft", "on_change")
    on_draft(TextChangeEvent(key="draft", value="buy milk"))
    assert app.state.draft == "buy milk"

    await _find_handler(module.view(app), "queue", "on_click")()
    assert app.state.queued == 1
    assert app.state.draft == ""
    assert app.state.log == ["buy milk"]
    assert bridge.calls[0]["capability"] == "offline.enqueue"
    assert bridge.calls[0]["args"]["url"] == "/api/log"

    # Replay drains the queue.
    await _find_handler(module.view(app), "replay", "on_click")()
    assert app.state.queued == 0
    assert "replayed 1" in app.state.status
