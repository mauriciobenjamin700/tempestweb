# Copy & Share — Native Capabilities 📋

Access the system **clipboard** and **share sheet** directly from typed Python — and learn how tempestweb connects Python code to native browser APIs.

---

## What you'll build

A copy-and-share demo featuring:

- 📄 A text snippet displayed on the screen
- 📋 A **Copy** button that writes the text to the OS clipboard
- 🔗 A **Share** button that opens the browser's native share sheet
- ⏳ A **Spinner** shown while the operation is in progress
- 💬 A status text that reflects the outcome: copied, shared, cancelled, unsupported, or error

!!! note "Note — what are native capabilities?"
    Native capabilities are browser Web APIs (Clipboard API, Web Share API, Geolocation API, etc.) accessed from typed Python. tempestweb routes each call to the correct browser — whether the browser is running Python directly (Mode A / WASM) or is separate from the Python server (Mode B / WebSocket).

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional):

- [Basic tutorial](../tutorial/index.en.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.en.md) — how `set_state` works
- [Execution modes](../tutorial/modes.en.md) — WASM vs. server

---

## Creating the project

Create the folder and app file:

```bash
mkdir -p examples/clipboard-share
touch examples/clipboard-share/app.py
```

---

## Step 1 — Understanding the native bridge

Before writing code, it is important to understand **why** a bridge exists.

Python has no direct access to the clipboard or the share sheet — those are browser resources. tempestweb solves this through a `NativeBridge`, which is the only difference between the two execution modes:

| Mode | Installed bridge | How it works |
|---|---|---|
| **A (WASM)** | `FFIBridge` | Calls `client/native/*.js` directly, in-process, no network |
| **B (server)** | `ProxyBridge` | Serialises the call, sends it to the browser over WebSocket, awaits the result |

!!! warning "Warning — bridge required at runtime"
    The functions `clipboard.write` and `share.share` raise `BrowserUnavailableError` if no bridge is installed when they are called. At runtime (Mode A or B) the bridge is installed automatically by the tempestweb bootstrap. **You do not need to call `install_bridge` in your application.** You only call `install_bridge` / `uninstall_bridge` in **tests** to inject a fake bridge.

In the diagram below, `NativeBridge` is the only piece that changes between modes — the `view` function does not know and does not need to know which bridge is installed:

```
view(app)
    │
    └── await clipboard.write(text)
              │
              └── send_native_call("clipboard.write", ...)
                        │
                        └── current_bridge().call(envelope)   ← SEAM
                                  │
                          ┌───────┴────────┐
                          │                │
                     FFIBridge        ProxyBridge
                 (Mode A: in-proc)  (Mode B: WebSocket)
                          │                │
                    client/native/    client/native/
                    clipboard.js      clipboard.js
                          │                │
                  navigator.clipboard.writeText(...)
```

---

## Step 2 — Defining the types and state

The example uses dependency injection so that tests can swap the real functions for fakes.

We define two callable types — `Copier` and `Sharer` — and store the concrete function as a field in the state:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import clipboard
from tempestweb.native.share import ShareOutcome, ShareResult
from tempestweb.native.share import share as _native_share

# ---------------------------------------------------------------------------
# Injected capability types
# ---------------------------------------------------------------------------

#: A coroutine that writes text to the clipboard. Injected for testability.
Copier = Callable[[str], Awaitable[None]]

#: A coroutine that opens the share sheet. Injected for testability.
Sharer = Callable[..., Awaitable[ShareResult]]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: The snippet shown to the user and offered for copy / share.
SNIPPET: str = "tempestweb — write UIs in typed Python, run them everywhere."


class Phase(StrEnum):
    """Lifecycle phase of the clipboard-share interaction.

    Attributes:
        IDLE: Nothing has been attempted yet.
        BUSY: A capability call is in flight.
        COPIED: The clipboard write succeeded.
        SHARED: The share sheet completed.
        ERROR: The capability raised an error.
    """

    IDLE = "idle"
    BUSY = "busy"
    COPIED = "copied"
    SHARED = "shared"
    ERROR = "error"


@dataclass
class ClipShareState:
    """Application state for the clipboard-share demo.

    Attributes:
        phase: Current lifecycle phase.
        share_outcome: The ShareOutcome from the last share attempt, or
            None if no share has been tried.
        error: Human-readable error message shown when phase is ERROR.
        copy: Injected clipboard-write coroutine (real default is the native cap).
        share_fn: Injected share coroutine (real default is the native cap).
    """

    phase: Phase = Phase.IDLE
    share_outcome: ShareOutcome | None = None
    error: str = ""
    copy: Copier = field(default=clipboard.write)
    share_fn: Sharer = field(default=_native_share)


def make_state() -> ClipShareState:
    """Build the initial, idle clipboard-share state.

    Returns:
        A fresh ClipShareState.
    """
    return ClipShareState()
```

!!! tip "Tip — dependency injection via dataclass field"
    By storing `copy` and `share_fn` as fields with real defaults, you get two things at once:

    1. **In production**, `make_state()` creates state with the real native functions — zero extra configuration.
    2. **In tests**, you replace the callables with fakes without monkey-patching: just pass `copy=fake_copy` when constructing the state.

    This pattern is especially valuable when the real function would need a bridge installed to avoid raising an exception.

Here is how the state machine evolves as the user acts:

```
IDLE ──────── click Copy ──────► BUSY ──── success ──► COPIED
  │                                  │
  │           click Share            └──── error ──────► ERROR
  └─────────────────────────────► BUSY ──── success ──► SHARED
                                       └──── error ──────► ERROR
```

---

## Step 3 — The async handlers

The handlers live **inside `view()`** because they need to capture `app` from the outer scope. Each one follows the same three-step pattern:

1. Transition to `BUSY` immediately (visual feedback).
2. `await` the native capability.
3. Transition to the final state (`COPIED`, `SHARED`, or `ERROR`).

```python
async def do_copy() -> None:
    """Copy the snippet to the OS clipboard.

    Transitions: IDLE/ERROR -> BUSY -> COPIED | ERROR.
    """
    app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
    try:
        await app.state.copy(SNIPPET)
    except Exception as exc:  # noqa: BLE001 — surface to UI
        msg = str(exc)

        def _on_copy_error(s: ClipShareState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_copy_error)
        return

    app.set_state(lambda s: setattr(s, "phase", Phase.COPIED))


async def do_share() -> None:
    """Open the OS share sheet.

    Transitions: IDLE/ERROR -> BUSY -> SHARED (outcome stored) | ERROR.
    """
    app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
    try:
        result: ShareResult = await app.state.share_fn(
            title="tempestweb",
            text=SNIPPET,
            url="https://github.com/tempest-framework/tempestweb",
        )
    except Exception as exc:  # noqa: BLE001 — surface to UI
        msg = str(exc)

        def _on_share_error(s: ClipShareState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_share_error)
        return

    def _on_shared(s: ClipShareState) -> None:
        s.phase = Phase.SHARED
        s.share_outcome = result.outcome

    app.set_state(_on_shared)
```

!!! info "Why catch a generic `Exception` here?"
    In production the share function may raise `NativeError` (from the bridge) or any network exception. Catching `Exception` and displaying the message in the UI is the correct behaviour for a demo: the user sees what happened. In production apps you may want to be more selective and separate error types.

!!! tip "Tip — `ShareOutcome` is not an exception"
    `ShareOutcome.CANCELLED` and `ShareOutcome.UNSUPPORTED` are returned as normal values inside `ShareResult`, never as exceptions. The Web Share API degrades gracefully: if the browser does not support `navigator.share`, the JS returns `{"outcome": "unsupported"}` rather than raising an error.

---

## Step 4 — The status text

The status text is derived from the current `phase` and `share_outcome`. It is computed inside `view()` on every render — zero extra state:

```python
phase = app.state.phase

if phase is Phase.IDLE:
    status_text = "Choose an action below."
elif phase is Phase.BUSY:
    status_text = "Working…"
elif phase is Phase.COPIED:
    status_text = "Copied to clipboard!"
elif phase is Phase.SHARED:
    outcome = app.state.share_outcome
    if outcome is ShareOutcome.SHARED:
        status_text = "Shared successfully."
    elif outcome is ShareOutcome.CANCELLED:
        status_text = "Share cancelled."
    else:
        # UNSUPPORTED — Web Share API missing in this browser
        status_text = "Sharing is not supported in this browser."
else:
    # ERROR
    status_text = f"Error: {app.state.error}"
```

| `phase` | `share_outcome` | Text displayed |
|---|---|---|
| `IDLE` | — | `Choose an action below.` |
| `BUSY` | — | `Working…` |
| `COPIED` | — | `Copied to clipboard!` |
| `SHARED` | `SHARED` | `Shared successfully.` |
| `SHARED` | `CANCELLED` | `Share cancelled.` |
| `SHARED` | `UNSUPPORTED` | `Sharing is not supported in this browser.` |
| `ERROR` | — | `Error: <message>` |

---

## Step 5 — Assembling the widget tree

The action row shows a `Spinner` when `BUSY`, or the two buttons in all other states. This eliminates double-clicks without needing a separate `disabled` field:

```python
is_busy = phase is Phase.BUSY
action_children: list[Widget] = []

if is_busy:
    action_children.append(Spinner(key="spinner"))
else:
    action_children.extend(
        [
            Button(
                label="Copy",
                on_click=do_copy,
                key="copy-btn",
            ),
            Button(
                label="Share",
                on_click=do_share,
                key="share-btn",
            ),
        ]
    )

actions: Widget = Row(
    style=Style(gap=8.0),
    children=action_children,
    key="actions",
)

return Column(
    style=Style(gap=16.0, padding=Edge.all(20.0)),
    children=[
        Text(content="Copy & Share", style=Style(font_size=22.0), key="title"),
        Text(
            content=SNIPPET,
            style=Style(font_size=14.0),
            key="snippet",
        ),
        actions,
        Text(content=status_text, key="status"),
    ],
)
```

!!! tip "Tip — Spinner as double-click protection"
    Replacing the buttons with a `Spinner` during `BUSY` is a natural protection: there is no button to click, so there is no way to trigger a second concurrent operation. It is simpler and safer than maintaining a separate boolean `loading` field alongside `phase`.

---

## The complete app

Here is the full file, ready to copy:

```python
"""Copy & share — exercises the clipboard and share native capabilities.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The demo presents a short text snippet alongside two action buttons:

* **Copy** — writes the snippet to the OS clipboard via
  ``native.clipboard.write``.  The action status is stored in state so the UI
  reflects whether the write succeeded, failed or is still pending.
* **Share** — opens the platform share sheet via ``native.share.share`` and
  renders the :class:`~tempestweb.native.share.ShareOutcome` back to the user:
  ``shared``, ``cancelled``, or ``unsupported`` (the API does not exist in
  the current browser).

Both capability callables are **injected into** :class:`ClipShareState` with
real defaults so that:

1. ``build(view(app))`` is green with **no bridge installed** — the initial
   mount only reads state; it never calls the capabilities.
2. Tests swap in a ``FakeBridge`` and drive the async handlers end-to-end,
   asserting real state transitions.

State machine
-------------
* ``Phase.IDLE``    — nothing has been attempted yet.
* ``Phase.BUSY``    — a capability call is in flight (spinner or disabled feedback).
* ``Phase.COPIED``  — clipboard write succeeded.
* ``Phase.SHARED``  — share sheet completed (outcome stored separately).
* ``Phase.ERROR``   — the capability raised :class:`~tempestweb.native.NativeError`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import clipboard
from tempestweb.native.share import ShareOutcome, ShareResult
from tempestweb.native.share import share as _native_share

# ---------------------------------------------------------------------------
# Injected capability types
# ---------------------------------------------------------------------------

#: A coroutine that writes text to the clipboard. Injected for testability.
Copier = Callable[[str], Awaitable[None]]

#: A coroutine that opens the share sheet. Injected for testability.
Sharer = Callable[..., Awaitable[ShareResult]]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: The snippet shown to the user and offered for copy / share.
SNIPPET: str = "tempestweb — write UIs in typed Python, run them everywhere."


class Phase(StrEnum):
    """Lifecycle phase of the clipboard-share interaction.

    Attributes:
        IDLE: Nothing has been attempted yet.
        BUSY: A capability call is in flight.
        COPIED: The clipboard write succeeded.
        SHARED: The share sheet completed.
        ERROR: The capability raised an error.
    """

    IDLE = "idle"
    BUSY = "busy"
    COPIED = "copied"
    SHARED = "shared"
    ERROR = "error"


@dataclass
class ClipShareState:
    """Application state for the clipboard-share demo.

    Attributes:
        phase: Current lifecycle phase.
        share_outcome: The :class:`~tempestweb.native.share.ShareOutcome` from
            the last share attempt, or ``None`` if no share has been tried.
        error: Human-readable error message shown when ``phase`` is ERROR.
        copy: Injected clipboard-write coroutine (real default is the native cap).
        share_fn: Injected share coroutine (real default is the native cap).
    """

    phase: Phase = Phase.IDLE
    share_outcome: ShareOutcome | None = None
    error: str = ""
    copy: Copier = field(default=clipboard.write)
    share_fn: Sharer = field(default=_native_share)


def make_state() -> ClipShareState:
    """Build the initial, idle clipboard-share state.

    Returns:
        A fresh :class:`ClipShareState`.
    """
    return ClipShareState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[ClipShareState]) -> Widget:
    """Render the clipboard-share UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def do_copy() -> None:
        """Copy the snippet to the OS clipboard.

        Transitions: IDLE/ERROR -> BUSY -> COPIED | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            await app.state.copy(SNIPPET)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_copy_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_copy_error)
            return

        app.set_state(lambda s: setattr(s, "phase", Phase.COPIED))

    async def do_share() -> None:
        """Open the OS share sheet.

        Transitions: IDLE/ERROR -> BUSY -> SHARED (outcome stored) | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            result: ShareResult = await app.state.share_fn(
                title="tempestweb",
                text=SNIPPET,
                url="https://github.com/tempest-framework/tempestweb",
            )
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_share_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_share_error)
            return

        def _on_shared(s: ClipShareState) -> None:
            s.phase = Phase.SHARED
            s.share_outcome = result.outcome

        app.set_state(_on_shared)

    # ------------------------------------------------------------------
    # Status text — reflects the last action
    # ------------------------------------------------------------------

    phase = app.state.phase

    if phase is Phase.IDLE:
        status_text = "Choose an action below."
    elif phase is Phase.BUSY:
        status_text = "Working…"
    elif phase is Phase.COPIED:
        status_text = "Copied to clipboard!"
    elif phase is Phase.SHARED:
        outcome = app.state.share_outcome
        if outcome is ShareOutcome.SHARED:
            status_text = "Shared successfully."
        elif outcome is ShareOutcome.CANCELLED:
            status_text = "Share cancelled."
        else:
            # UNSUPPORTED — Web Share API missing in this browser
            status_text = "Sharing is not supported in this browser."
    else:
        # ERROR
        status_text = f"Error: {app.state.error}"

    # ------------------------------------------------------------------
    # Action buttons row
    # ------------------------------------------------------------------

    is_busy = phase is Phase.BUSY
    action_children: list[Widget] = []

    if is_busy:
        action_children.append(Spinner(key="spinner"))
    else:
        action_children.extend(
            [
                Button(
                    label="Copy",
                    on_click=do_copy,
                    key="copy-btn",
                ),
                Button(
                    label="Share",
                    on_click=do_share,
                    key="share-btn",
                ),
            ]
        )

    actions: Widget = Row(
        style=Style(gap=8.0),
        children=action_children,
        key="actions",
    )

    # ------------------------------------------------------------------
    # Assemble the full view
    # ------------------------------------------------------------------

    return Column(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=[
            Text(content="Copy & Share", style=Style(font_size=22.0), key="title"),
            Text(
                content=SNIPPET,
                style=Style(font_size=14.0),
                key="snippet",
            ),
            actions,
            Text(content=status_text, key="status"),
        ],
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/clipboard-share
```

Python runs **inside the browser** via Pyodide. The `FFIBridge` is installed automatically by the WASM bootstrap and calls `client/native/clipboard.js` and `client/native/share.js` in-process.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/clipboard-share
```

Python runs on the server; the `ProxyBridge` is installed automatically by the WebSocket session. Each call to `clipboard.write` or `share.share` travels to the browser over the WebSocket, the JS executes the Web API, and the result comes back to Python over the same channel.

!!! check "Verification"
    In either mode, you should see:

    1. Title **Copy & Share** and the text snippet
    2. Two buttons: **Copy** and **Share**
    3. Initial status text: `Choose an action below.`
    4. Click **Copy** → buttons disappear, spinner appears, then: `Copied to clipboard!`
    5. Click **Share** → spinner → browser native share sheet → `Shared successfully.` (or `Share cancelled.` if dismissed without sharing)
    6. In browsers without the Web Share API (e.g. Firefox desktop) → `Sharing is not supported in this browser.`

!!! warning "Warning — secure context required"
    The Clipboard API and the Web Share API require **HTTPS** (or `localhost`). When running on `localhost` with the tempestweb dev server, everything works. In production, make sure you are serving over HTTPS, otherwise the bridge returns a `NativeError` with code `insecure_context`.

---

## Testing with fake bridges 🧪

Since the handlers call native capabilities, tests cannot simply import and call `view()` and expect everything to work — they would need a real bridge (and a real browser). The solution is dependency injection: you install a fake bridge before the test and remove it afterwards.

### FakeBridge — scripted behaviour

```python
from typing import Any

from tempestweb.native import install_bridge, uninstall_bridge


class FakeBridge:
    """Fake native bridge for clipboard and share capabilities.

    Records the last envelope received and returns scripted responses so the
    tests run with no real browser present.

    Attributes:
        share_outcome: The share outcome string to return (default "shared").
        calls: Ordered list of capability names that were dispatched.
    """

    def __init__(self, *, share_outcome: str = "shared") -> None:
        """Initialise the bridge.

        Args:
            share_outcome: The ShareOutcome value to return from share.share.
        """
        self.share_outcome: str = share_outcome
        self.calls: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Handle a native capability call.

        Args:
            envelope: The native_call envelope dispatched by the capability wrapper.

        Returns:
            A scripted ok / value response dict.
        """
        cap: str = envelope["capability"]
        self.calls.append(cap)

        if cap == "clipboard.write":
            return {"ok": True, "value": {}}
        if cap == "share.share":
            return {"ok": True, "value": {"outcome": self.share_outcome}}

        return {"ok": False, "error": "unavailable", "message": f"no fake for {cap}"}
```

### ErrorBridge — simulates permission denial

```python
class ErrorBridge:
    """Fake bridge that always returns an error response.

    Used to verify that the ERROR phase is surfaced correctly in the UI.
    """

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Return a permission_denied error for every call.

        Args:
            envelope: Ignored; every call returns an error.

        Returns:
            An ok: False response.
        """
        return {
            "ok": False,
            "error": "permission_denied",
            "message": "permission denied by user",
        }
```

### The 8 tests

The complete test suite covers every path through the state machine:

```python
from __future__ import annotations

from typing import Any

import pytest

from tempest_core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.share import ShareOutcome


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


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Locate a handler callable by widget key and attribute name.

    Args:
        widget: The root widget returned by view(app).
        key: The key of the target widget.
        attr: The handler attribute name (e.g. "on_click").

    Returns:
        The handler callable.

    Raises:
        AssertionError: If no matching widget/handler is found.
    """
    stack: list[Any] = [widget]
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == key:
            handler = getattr(current, attr, None)
            if handler is not None:
                return handler
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError(f"no widget with key={key!r} and handler {attr!r}")


def _status_text(node: Node) -> str:
    """Return the content prop of the status Text node.

    Args:
        node: The root IR node of the built tree.

    Returns:
        The status text string.

    Raises:
        AssertionError: If no status node is found.
    """
    for n in _walk(node):
        if n.key == "status":
            return str(n.props.get("content", ""))
    raise AssertionError("no node with key='status' found")


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:  # noqa: ANN401
    """Guarantee no bridge leaks between tests."""
    uninstall_bridge()
    yield
    uninstall_bridge()


# -- Tests -------------------------------------------------------------------


def test_initial_build_no_bridge(module: Any, app: App[Any]) -> None:
    """build(view(app)) yields a valid Node tree with no bridge installed."""
    node = build(module.view(app))
    assert isinstance(node, Node)
    assert node.type
    assert node.children


def test_initial_status_is_idle(module: Any, app: App[Any]) -> None:
    """The status Text reflects the IDLE phase on first mount."""
    node = build(module.view(app))
    assert _status_text(node) == "Choose an action below."


async def test_copy_handler_transitions_to_copied(module: Any, app: App[Any]) -> None:
    """Driving do_copy with a fake bridge transitions IDLE -> COPIED."""
    bridge = FakeBridge()
    install_bridge(bridge)

    idle_node = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "copied"
    copied_node = build(module.view(app))
    assert _status_text(copied_node) == "Copied to clipboard!"
    assert _status_text(copied_node) != _status_text(idle_node)
    assert "clipboard.write" in bridge.calls


async def test_share_handler_shared_outcome(module: Any, app: App[Any]) -> None:
    """Driving do_share with outcome 'shared' transitions IDLE -> SHARED."""
    bridge = FakeBridge(share_outcome="shared")
    install_bridge(bridge)

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.phase.value == "shared"
    assert app.state.share_outcome is ShareOutcome.SHARED
    node = build(module.view(app))
    assert _status_text(node) == "Shared successfully."
    assert "share.share" in bridge.calls


async def test_share_handler_cancelled_outcome(module: Any, app: App[Any]) -> None:
    """A cancelled share sheet transitions to SHARED with CANCELLED outcome."""
    install_bridge(FakeBridge(share_outcome="cancelled"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.CANCELLED
    node = build(module.view(app))
    assert _status_text(node) == "Share cancelled."


async def test_share_handler_unsupported_outcome(module: Any, app: App[Any]) -> None:
    """An unsupported browser returns UNSUPPORTED outcome without raising."""
    install_bridge(FakeBridge(share_outcome="unsupported"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.UNSUPPORTED
    node = build(module.view(app))
    assert "not supported" in _status_text(node)


async def test_copy_error_transitions_to_error_phase(
    module: Any, app: App[Any]
) -> None:
    """A NativeError during clipboard.write transitions to the ERROR phase."""
    install_bridge(ErrorBridge())

    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "error"
    node = build(module.view(app))
    status = _status_text(node)
    assert status.startswith("Error:")


async def test_tree_changes_between_idle_and_copied(module: Any, app: App[Any]) -> None:
    """The rebuilt tree differs after a successful copy (diff-friendly)."""
    from tempest_core import diff

    install_bridge(FakeBridge())

    before = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()
    after = build(module.view(app))

    patches = diff(before, after)
    assert patches, "expected at least one patch after a state transition"
```

!!! tip "Tip — `autouse=True` on `_clean_bridge`"
    The `_clean_bridge` fixture cleans up the bridge before and after **each** test using `autouse=True`. This ensures that a test that forgot to uninstall the bridge does not contaminate the next one. It is a good practice in any test suite that uses `install_bridge`.

---

## Automated verification ✅

Run all four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All should pass green. The example was specifically designed to be `mypy --strict` clean — every variable, parameter, and return type is explicitly annotated.

---

## How it works under the hood

### The full cycle of a native call

```
1. User clicks "Copy"
        │
        ▼
2. do_copy() called
        │
        ▼
3. app.set_state(phase=BUSY) → re-render → Spinner appears
        │
        ▼
4. await app.state.copy(SNIPPET)
        │           (= clipboard.write in production)
        │
        ▼
5. send_native_call("clipboard.write", {"text": SNIPPET})
        │
        ▼
6. current_bridge().call(envelope)
        │
   ┌────┴────────────────────────────────┐
   │ Mode A: FFIBridge                    │ Mode B: ProxyBridge
   │ calls JS in-process                  │ sends frame over WS
   │ (no network, no round-trip)          │ awaits native_result
   └──────────────────────────────────────┘
        │
        ▼
7. navigator.clipboard.writeText(SNIPPET)  [in the browser]
        │
        ▼
8. Result returns to Python
        │
        ▼
9. app.set_state(phase=COPIED) → re-render → "Copied to clipboard!"
```

### Why is `Phase` a `StrEnum`?

`StrEnum` lets you compare `app.state.phase.value == "copied"` in tests (readable string) **and** use `phase is Phase.COPIED` in the view (identity comparison, zero allocation). The string value is also natively JSON-serialisable — useful for logging and telemetry.

### Why are the handlers `async`?

Native capabilities are I/O operations: Python needs to suspend while the browser executes the Web API and returns the result. Using `await` is the natural path — the tempestweb asyncio event loop manages the suspension and resumption without blocking other in-progress renders.

---

## Recap

In this tutorial you learned:

- ✅ What a `NativeBridge` is and why it is the only difference between Mode A and Mode B
- ✅ How to use `clipboard.write` and `share.share` from typed Python
- ✅ How to model an async flow with `Phase` (IDLE → BUSY → COPIED/SHARED/ERROR)
- ✅ How to inject capabilities into state to make handlers testable without a browser
- ✅ How to use `FakeBridge` and `ErrorBridge` to test every path through the state machine
- ✅ Why `ShareOutcome.CANCELLED` and `ShareOutcome.UNSUPPORTED` are normal values, not exceptions

---

## Next steps

Try extending the example:

- 💡 Add a **Read** button that reads the current clipboard text with `clipboard.read()`
- 💡 Disable the **Share** button with `is_share_supported()` when the Web Share API is unavailable, instead of showing a message after the click
- 💡 Explore the [PWA + WebPush](./notification-center.en.md) example to see other native capabilities in action
- 💡 See [Execution modes](../tutorial/modes.en.md) to understand in depth how `FFIBridge` and `ProxyBridge` differ
