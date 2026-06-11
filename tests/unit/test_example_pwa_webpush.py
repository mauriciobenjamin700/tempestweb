"""Tests for examples/pwa-webpush — PWA install + WebPush consent flow.

Two independent test groups:

A. **App/view tests** — drive the async handlers through a :class:`FakeBridge`
   that returns scripted envelopes for ``notifications.request_permission`` and
   ``notifications.subscribe``. Each test asserts a real state transition *and*
   that the rebuilt widget tree reflects the new phase (e.g. the subscribe button
   appears after permission is granted, and subscription details appear once
   fully subscribed).

B. **PWA build tests** — call ``build_pwa.main(tmp_path)`` and assert that
   ``validate_installable`` returns ``[]`` (fully installable), the manifest file
   exists and is valid JSON, and the icon files exist.

The :class:`FakeBridge` fixture is installed via an ``autouse`` fixture so no
test ever leaks bridge state to neighbours.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.notifications import NotificationPermission
from tempestweb.pwa import validate_installable

# ---------------------------------------------------------------------------
# Helpers to load the example modules without polluting sys.path
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load(name: str, file: str) -> ModuleType:
    """Import a file from the examples/pwa-webpush directory by filename.

    Args:
        name: Unique module name to register in ``sys.modules``.
        file: Filename under ``examples/pwa-webpush/`` (e.g. ``"app.py"``).

    Returns:
        The imported module.
    """
    module_name = f"_example_pwa_webpush_{name}"
    path = EXAMPLES_DIR / "pwa-webpush" / file
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load both modules once per session for speed; they are stateless at import time.
_app_mod = _load("app", "app.py")
_build_mod = _load("build_pwa", "build_pwa.py")


def _make_app() -> App[Any]:
    """Construct an App around the example's make_state/view.

    Returns:
        An App whose apply_patches is a no-op.
    """
    return App(
        state=_app_mod.make_state(),
        view=_app_mod.view,
        apply_patches=lambda _patches: None,
    )


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a list of nodes (pre-order).

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _keys(node: Node) -> set[str]:
    """Return the set of widget keys present in the subtree.

    Args:
        node: The root of the subtree.

    Returns:
        A set of all non-empty key strings found in the tree.
    """
    return {n.key for n in _walk(node) if n.key}


# ---------------------------------------------------------------------------
# Fake bridge fixture
# ---------------------------------------------------------------------------


class _FakeBridge:
    """Minimal fake FFI bridge for notification capabilities.

    Returns scripted responses for ``notifications.request_permission`` and
    ``notifications.subscribe``. Any other capability gets a generic error so
    tests fail loudly if an unexpected capability is called.
    """

    def __init__(
        self,
        permission: str = "granted",
        subscription: dict[str, Any] | None = None,
        fail_cap: str | None = None,
    ) -> None:
        """Initialise the fake bridge.

        Args:
            permission: Value for the ``permission`` field returned by
                ``notifications.request_permission`` (default: ``"granted"``).
            subscription: Dict returned for ``notifications.subscribe``.
                Defaults to a minimal endpoint + keys dict.
            fail_cap: If set, return ``{"ok": False}`` for this capability name.
        """
        self.permission = permission
        self.subscription: dict[str, Any] = subscription or {
            "endpoint": "https://push.example/sub/abc123",
            "keys": {"p256dh": "BKEY", "auth": "AUTH"},
        }
        self.fail_cap = fail_cap
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a fake native call envelope.

        Args:
            envelope: The ``native_call`` envelope from the framework.

        Returns:
            A ``{"ok": True, "value": {...}}`` or ``{"ok": False, ...}`` dict.
        """
        self.calls.append(envelope)
        cap: str = envelope.get("capability", "")

        if self.fail_cap and cap == self.fail_cap:
            return {"ok": False, "error": "test_error", "message": "forced failure"}

        if cap == "notifications.request_permission":
            return {"ok": True, "value": {"permission": self.permission}}
        if cap == "notifications.subscribe":
            return {"ok": True, "value": self.subscription}
        if cap == "notifications.unsubscribe":
            return {"ok": True, "value": {"unsubscribed": True}}
        if cap == "notifications.notify":
            return {"ok": True, "value": {}}

        return {"ok": False, "error": "unavailable", "message": f"no mock for {cap}"}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Install and teardown a clean bridge state around every test.

    Yields:
        Nothing — side-effect only.
    """
    uninstall_bridge()
    yield
    uninstall_bridge()


# ===========================================================================
# Group A — App / view tests
# ===========================================================================


def test_initial_build_requires_no_bridge() -> None:
    """build(view(app)) must succeed with no bridge installed.

    The test verifies the DETERMINISM RULE: the initial render must not
    invoke any native capability.
    """
    app = _make_app()
    node = build(_app_mod.view(app))
    assert node.type  # non-empty type string
    assert node.children  # at least the title + subtitle are rendered
    keys = _keys(node)
    assert "title" in keys
    assert "status-text" in keys
    assert "btn-enable" in keys  # the initial "Enable notifications" button


async def test_request_permission_granted_transitions_to_granted() -> None:
    """Pressing 'Enable notifications' with a granted bridge -> GRANTED phase."""
    bridge = _FakeBridge(permission="granted")
    install_bridge(bridge)

    app = _make_app()
    # Find the handle_request_permission handler
    initial_node = build(_app_mod.view(app))
    keys = _keys(initial_node)
    assert "btn-enable" in keys, "Enable button must exist in IDLE phase"

    # Locate and call the on_click handler from the button in the tree
    def _find_button(node: Node, key: str) -> Node | None:
        if node.key == key:
            return node
        for child in node.children:
            found = _find_button(child, key)
            if found is not None:
                return found
        return None

    btn_node = _find_button(initial_node, "btn-enable")
    assert btn_node is not None
    handler = btn_node.props.get("on_click")
    assert handler is not None, "on_click must be set on the enable button"
    await handler()

    # State must now be GRANTED
    assert app.state.phase == _app_mod.Phase.GRANTED

    # Rebuild and check the subscribe button is now visible
    updated_node = build(_app_mod.view(app))
    updated_keys = _keys(updated_node)
    assert "btn-subscribe" in updated_keys, (
        "Subscribe button must appear in GRANTED phase"
    )
    assert "btn-enable" not in updated_keys, (
        "Enable button must not appear in GRANTED phase"
    )

    # Verify exactly one native call was made with the right capability
    assert len(bridge.calls) == 1
    assert bridge.calls[0]["capability"] == "notifications.request_permission"


async def test_request_permission_denied_transitions_to_denied() -> None:
    """Pressing 'Enable notifications' with a denied bridge -> DENIED phase."""
    bridge = _FakeBridge(permission="denied")
    install_bridge(bridge)

    app = _make_app()

    def _find_button(node: Node, key: str) -> Node | None:
        if node.key == key:
            return node
        for child in node.children:
            found = _find_button(child, key)
            if found is not None:
                return found
        return None

    initial_node = build(_app_mod.view(app))
    handler = _find_button(initial_node, "btn-enable")
    assert handler is not None
    on_click = handler.props.get("on_click")
    assert on_click is not None
    await on_click()

    assert app.state.phase == _app_mod.Phase.DENIED

    # UI shows both enable + retry buttons in DENIED phase
    updated_node = build(_app_mod.view(app))
    updated_keys = _keys(updated_node)
    assert "btn-enable" in updated_keys
    assert "btn-retry" in updated_keys


async def test_subscribe_transitions_to_subscribed() -> None:
    """After GRANTED, pressing 'Subscribe to push' -> SUBSCRIBED with endpoint."""
    bridge = _FakeBridge(
        permission="granted",
        subscription={
            "endpoint": "https://push.example/sub/xyz999",
            "keys": {"p256dh": "BKEY", "auth": "AUTH"},
        },
    )
    install_bridge(bridge)

    # Inject simple coroutines so we can drive both steps without relying on
    # the process-global bridge for the permission step.
    async def _fake_request_permission() -> NotificationPermission:
        return NotificationPermission.GRANTED

    async def _actual_subscribe(vapid_key: str) -> dict[str, Any]:
        result = await bridge.call(
            {
                "kind": "native_call",
                "call_id": "t2",
                "capability": "notifications.subscribe",
                "args": {"vapid_public_key": vapid_key},
            }
        )
        return dict(result.get("value", {}))

    app = _make_app()
    # Inject simpler callables for deterministic control
    app.state.request_permission = _fake_request_permission
    app.state.subscribe = _actual_subscribe

    # Step 1: go to GRANTED
    initial_node = build(_app_mod.view(app))

    def _find_on_click(node: Node, key: str) -> Any:
        if node.key == key:
            return node.props.get("on_click")
        for child in node.children:
            found = _find_on_click(child, key)
            if found is not None:
                return found
        return None

    on_enable = _find_on_click(initial_node, "btn-enable")
    assert on_enable is not None
    await on_enable()
    assert app.state.phase == _app_mod.Phase.GRANTED

    # Step 2: subscribe
    granted_node = build(_app_mod.view(app))
    on_subscribe = _find_on_click(granted_node, "btn-subscribe")
    assert on_subscribe is not None
    await on_subscribe()

    assert app.state.phase == _app_mod.Phase.SUBSCRIBED
    assert app.state.subscription.get("endpoint") == "https://push.example/sub/xyz999"

    # UI shows subscription details
    subscribed_node = build(_app_mod.view(app))
    subscribed_keys = _keys(subscribed_node)
    assert "sub-details" in subscribed_keys
    assert "btn-reset" in subscribed_keys


async def test_reset_returns_to_idle() -> None:
    """Pressing 'Reset' from SUBSCRIBED returns the app to IDLE phase."""
    bridge = _FakeBridge(permission="granted")
    install_bridge(bridge)

    app = _make_app()

    async def _req_perm() -> NotificationPermission:
        return NotificationPermission.GRANTED

    async def _subscribe(vapid_key: str) -> dict[str, Any]:
        return {"endpoint": "https://push.example/sub/reset_test", "keys": {}}

    app.state.request_permission = _req_perm
    app.state.subscribe = _subscribe

    def _find_on_click(node: Node, key: str) -> Any:
        if node.key == key:
            return node.props.get("on_click")
        for child in node.children:
            found = _find_on_click(child, key)
            if found is not None:
                return found
        return None

    # Drive to SUBSCRIBED
    node0 = build(_app_mod.view(app))
    await _find_on_click(node0, "btn-enable")()
    node1 = build(_app_mod.view(app))
    await _find_on_click(node1, "btn-subscribe")()
    assert app.state.phase == _app_mod.Phase.SUBSCRIBED

    # Press reset
    node2 = build(_app_mod.view(app))
    on_reset = _find_on_click(node2, "btn-reset")
    assert on_reset is not None
    on_reset()  # handle_reset is synchronous

    assert app.state.phase == _app_mod.Phase.IDLE
    assert app.state.subscription == {}
    assert app.state.error == ""

    # UI is back to the initial button
    node3 = build(_app_mod.view(app))
    assert "btn-enable" in _keys(node3)


async def test_permission_error_transitions_to_error() -> None:
    """If request_permission raises, the app moves to ERROR phase."""
    app = _make_app()

    async def _failing_req() -> NotificationPermission:
        raise RuntimeError("bridge exploded")

    app.state.request_permission = _failing_req

    def _find_on_click(node: Node, key: str) -> Any:
        if node.key == key:
            return node.props.get("on_click")
        for child in node.children:
            found = _find_on_click(child, key)
            if found is not None:
                return found
        return None

    node = build(_app_mod.view(app))
    handler = _find_on_click(node, "btn-enable")
    assert handler is not None
    await handler()

    assert app.state.phase == _app_mod.Phase.ERROR
    assert "bridge exploded" in app.state.error

    # Error phase shows try-again button
    error_node = build(_app_mod.view(app))
    assert "btn-error-reset" in _keys(error_node)


# ===========================================================================
# Group B — PWA build tests
# ===========================================================================


def test_build_pwa_main_produces_installable_manifest(tmp_path: Path) -> None:
    """build_pwa.main writes a manifest that passes validate_installable."""
    result = _build_mod.main(tmp_path)

    manifest_path = result["manifest"][0]
    assert isinstance(manifest_path, Path), "manifest path must be a Path"
    assert manifest_path.exists(), "manifest.webmanifest must exist on disk"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_installable(manifest)
    assert errors == [], f"Expected installable manifest, got errors: {errors}"


def test_build_pwa_main_writes_icon_files(tmp_path: Path) -> None:
    """build_pwa.main(tmp_path) must write the full icon set under icons/."""
    result = _build_mod.main(tmp_path)

    icon_paths = result["icons"]
    assert len(icon_paths) >= 4, (
        "At least 4 icons (192/512 plain + maskable) must be written"
    )
    for p in icon_paths:
        assert isinstance(p, Path), "Each icon path must be a Path"
        assert p.exists(), f"Icon file missing: {p}"
        data = p.read_bytes()
        assert data[:4] == b"\x89PNG", f"{p.name} is not a valid PNG"


def test_build_pwa_manifest_fields(tmp_path: Path) -> None:
    """The written manifest must carry the pwa-webpush app metadata."""
    _build_mod.main(tmp_path)
    manifest_path = tmp_path / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "PWA WebPush Demo"
    assert manifest["short_name"] == "WebPush"
    assert manifest["display"] == "standalone"
    assert manifest.get("start_url") == "/"
    # validate_installable is the canonical check; the above are spot-checks
    assert validate_installable(manifest) == []


def test_build_pwa_validate_installable_direct() -> None:
    """validate_installable can be driven directly from build_manifest."""
    from tempestweb.pwa import build_manifest

    manifest = build_manifest(_build_mod.OPTIONS)
    errors = validate_installable(manifest)
    assert errors == [], f"Expected [], got {errors}"
