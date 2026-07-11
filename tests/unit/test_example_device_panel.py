"""Tests for examples/device-panel — the Tier-1 capabilities showcase.

Verifies the initial mount is bridge-free and that driving the async handlers
through a scripted bridge calls the right native capabilities and reflects them
in the panel state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempest_core import App, build
from tempestweb.native import install_bridge, uninstall_bridge

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load() -> ModuleType:
    path = EXAMPLES_DIR / "device-panel" / "app.py"
    spec = importlib.util.spec_from_file_location("_example_device_panel", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_example_device_panel"] = module
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
        self.calls: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        cap = envelope["capability"]
        self.calls.append(cap)
        if cap == "fullscreen.enter":
            return {"ok": True, "value": {"active": True}}
        if cap == "network.state":
            return {
                "ok": True,
                "value": {
                    "online": True,
                    "effective_type": "4g",
                    "downlink": 10.0,
                    "rtt": 50,
                    "save_data": False,
                },
            }
        if cap == "wakelock.request":
            return {"ok": True, "value": {"id": "w1"}}
        # vibration.vibrate and the rest return an empty ok value.
        return {"ok": True, "value": {}}


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


async def test_buttons_drive_capabilities() -> None:
    module = _load()
    bridge = _ScriptedBridge()
    install_bridge(bridge)
    app = _make_app(module)

    await _find_handler(module.view(app), "buzz", "on_click")()
    assert app.state.status == "buzzed"
    assert "vibration.vibrate" in bridge.calls

    await _find_handler(module.view(app), "awake", "on_click")()
    assert app.state.awake is True
    assert "wakelock.request" in bridge.calls

    await _find_handler(module.view(app), "fs", "on_click")()
    assert "fullscreen=True" in app.state.status
    assert "fullscreen.enter" in bridge.calls

    await _find_handler(module.view(app), "net", "on_click")()
    assert "4g" in app.state.network
    assert "network.state" in bridge.calls
