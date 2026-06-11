# PWA Install + WebPush — Push Notifications in the Browser 📱

Build an **installable** app that asks the user for notification permission and,
once granted, creates a **WebPush** subscription — all written in pure Python,
without a single line of application JavaScript. The same code runs in
**Mode A** (Python in the browser via Pyodide) and **Mode B** (Python on the
server via FastAPI + WebSocket).

---

## What you'll build

A PWA/WebPush consent flow with **7 phases**:

| Phase | Description |
|---|---|
| `IDLE` | Initial state — the user has not interacted yet |
| `REQUESTING` | Waiting for the browser permission prompt response |
| `DENIED` | The user blocked notifications |
| `GRANTED` | Permission granted; subscription not yet requested |
| `SUBSCRIBING` | Waiting for the push subscription to be created in the browser |
| `SUBSCRIBED` | Fully subscribed; `subscription` dict available |
| `ERROR` | Unexpected error; `error` field populated |

You'll also generate the **PWA build artifacts** — `manifest.webmanifest` plus a
set of valid PNG icons — with the `build_pwa.py` script, using pure Python only
(no Pillow, no external image dependencies).

!!! note "Note — where WebPush actually runs"
    The **browser** executes the Web Notifications API and `pushManager`. Python
    simply **sends** the request via `native_call` and **receives** the result. In
    **Mode A**, the call goes directly to `client/native/*.js` via Pyodide FFI. In
    **Mode B**, it travels over the WebSocket to the browser and back as a
    `native_result`. Your `view` never needs to know which mode it runs under.

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading (optional):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Execution modes](../tutorial/modes.md) — WASM vs. server
- [PWA and offline](../pwa.en.md) — the P track of the roadmap

---

## Creating the project

```bash
mkdir -p examples/pwa-webpush
touch examples/pwa-webpush/app.py
touch examples/pwa-webpush/build_pwa.py
```

---

## Step 1 — Modelling the state machine

Every tempestweb app starts with its **state**. Here the state is an explicit
phase machine with two injected callables. That injection is the key to
deterministic testing: you swap `request_permission` and `subscribe` with fakes
without needing a real browser.

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb.native import notifications
from tempestweb.native.notifications import NotificationPermission

#: VAPID public key used by default (placeholder; replace with your own in production).
DEMO_VAPID_KEY: str = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuB"
    "kr3qBUYIHBQFLXYp5Nksh8U"
)

#: Signature of the injected coroutine that requests permission.
PermissionRequester = Callable[[], Awaitable[NotificationPermission]]

#: Signature of the injected coroutine that creates the push subscription.
Subscriber = Callable[[str], Awaitable[dict[str, Any]]]


class Phase(StrEnum):
    """Lifecycle phases of the PWA WebPush consent flow."""

    IDLE = "idle"
    REQUESTING = "requesting"
    DENIED = "denied"
    GRANTED = "granted"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


@dataclass
class State:
    """Top-level state for the PWA WebPush demo app.

    Attributes:
        phase: Current lifecycle phase.
        subscription: The raw push subscription dict once subscribed.
        error: Human-readable error message, populated in ``Phase.ERROR``.
        vapid_key: VAPID public key passed to :func:`subscribe`.
        request_permission: Injected coroutine for the permission request.
        subscribe: Injected coroutine for the push subscription.
    """

    phase: Phase = Phase.IDLE
    subscription: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    vapid_key: str = DEMO_VAPID_KEY
    request_permission: PermissionRequester = notifications.request_permission
    subscribe: Subscriber = notifications.subscribe


def make_state() -> State:
    """Build the initial idle state with real capability defaults.

    Returns:
        A fresh :class:`State` in the ``IDLE`` phase.
    """
    return State()
```

!!! tip "Tip — dependency injection via dataclass"
    The `request_permission` and `subscribe` fields have the real callables
    (`tempestweb.native.notifications.*`) as default values, so the app works
    out of the box without any configuration. In tests, you override those fields
    with fakes — no monkey-patching, no global mocks.

---

## Step 2 — The async handlers

The handlers live inside `view()` as closures over `app`. Each one sets the
phase to a "loading" state immediately, calls the injected callable, and updates
state according to the result (or the error).

```python
async def handle_request_permission() -> None:
    """Ask the browser for notification permission and update state."""
    app.set_state(lambda s: setattr(s, "phase", Phase.REQUESTING))
    try:
        perm = await app.state.request_permission()
    except Exception as exc:  # noqa: BLE001 — surface error to the UI
        message = str(exc)

        def on_error(s: State) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(on_error)
        return

    if perm is NotificationPermission.GRANTED:
        app.set_state(lambda s: setattr(s, "phase", Phase.GRANTED))
    elif perm is NotificationPermission.DENIED:
        app.set_state(lambda s: setattr(s, "phase", Phase.DENIED))
    else:
        # DEFAULT — the user dismissed the prompt; stay at IDLE
        app.set_state(lambda s: setattr(s, "phase", Phase.IDLE))


async def handle_subscribe() -> None:
    """Subscribe to WebPush using the stored VAPID key and update state."""
    app.set_state(lambda s: setattr(s, "phase", Phase.SUBSCRIBING))
    try:
        sub = await app.state.subscribe(app.state.vapid_key)
    except Exception as exc:  # noqa: BLE001 — surface error to the UI
        message = str(exc)

        def on_error(s: State) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(on_error)
        return

    def on_subscribed(s: State) -> None:
        s.phase = Phase.SUBSCRIBED
        s.subscription = sub

    app.set_state(on_subscribed)


def handle_reset() -> None:
    """Reset state back to IDLE."""

    def reset(s: State) -> None:
        s.phase = Phase.IDLE
        s.subscription = {}
        s.error = ""

    app.set_state(reset)
```

!!! info "Note — `Phase.REQUESTING` and `Phase.SUBSCRIBING`"
    Setting the phase to "loading" **before** awaiting the callable ensures the UI
    shows a `Spinner` immediately. If you only updated after the `await`, the user
    would stare at an unresponsive button for the entire duration of the browser
    prompt.

---

## Step 3 — Building the widget tree

The `view` is pure: it reads `app.state`, decides which widgets to show, and
returns the tree. The reconciler computes the diff and updates the DOM with the
minimum number of changes.

```python
from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text


def view(app: App[State]) -> Widget:
    """Render the PWA/WebPush consent UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    # ... handlers defined here (see Step 2)

    phase = app.state.phase

    status_messages: dict[Phase, str] = {
        Phase.IDLE: "Notifications are not yet enabled.",
        Phase.REQUESTING: "Waiting for browser permission…",
        Phase.DENIED: (
            "Permission denied. You can re-enable notifications"
            " in your browser settings."
        ),
        Phase.GRANTED: (
            "Permission granted. You can now subscribe to push notifications."
        ),
        Phase.SUBSCRIBING: "Creating push subscription…",
        Phase.SUBSCRIBED: "Successfully subscribed to push notifications!",
        Phase.ERROR: f"Error: {app.state.error}",
    }

    status_text: Widget = Text(
        content=status_messages[phase],
        key="status-text",
    )

    children: list[Widget] = [
        Text(
            content="PWA WebPush Demo",
            style=Style(font_size=22.0),
            key="title",
        ),
        Text(
            content="Enable browser push notifications to receive real-time updates.",
            style=Style(font_size=14.0),
            key="subtitle",
        ),
        status_text,
    ]

    if phase is Phase.REQUESTING or phase is Phase.SUBSCRIBING:
        children.append(
            Row(
                style=Style(gap=8.0),
                children=[
                    Spinner(key="loading-spinner"),
                    Text(
                        content=(
                            "Requesting permission…"
                            if phase is Phase.REQUESTING
                            else "Subscribing…"
                        ),
                        key="loading-label",
                    ),
                ],
                key="loading-row",
            )
        )
    elif phase is Phase.IDLE or phase is Phase.DENIED:
        children.append(
            Button(
                label="Enable notifications",
                on_click=handle_request_permission,
                key="btn-enable",
            )
        )
        if phase is Phase.DENIED:
            children.append(
                Button(
                    label="Try again",
                    on_click=handle_request_permission,
                    key="btn-retry",
                )
            )
    elif phase is Phase.GRANTED:
        children.append(
            Button(
                label="Subscribe to push",
                on_click=handle_subscribe,
                key="btn-subscribe",
            )
        )
    elif phase is Phase.SUBSCRIBED:
        endpoint = app.state.subscription.get("endpoint", "")
        children.append(
            Column(
                style=Style(gap=4.0, padding=Edge.all(12.0)),
                children=[
                    Text(content="Subscription endpoint:", key="sub-label"),
                    Text(
                        content=endpoint[:64] + "…" if len(endpoint) > 64 else endpoint,
                        key="sub-endpoint",
                    ),
                ],
                key="sub-details",
            )
        )
        children.append(
            Button(
                label="Reset",
                on_click=handle_reset,
                key="btn-reset",
            )
        )
    elif phase is Phase.ERROR:
        children.append(
            Button(
                label="Try again",
                on_click=handle_reset,
                key="btn-error-reset",
            )
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
```

!!! tip "Tip — `if phase is Phase.X` vs `elif`"
    The `if / elif` chain in `view` is the state machine **read backwards**: instead
    of transitions, you declare *what to show in each phase*. The reconciler detects
    differences between renders and updates only what changed in the DOM.

---

## Step 4 — The PWA build script

`build_pwa.py` generates the installable artifacts — `manifest.webmanifest` and
the icon set — and validates them against Chromium/Lighthouse criteria. Run it
separately before deploying.

```python
"""PWA build script — emits manifest.webmanifest + icon set."""

from __future__ import annotations

import json
from pathlib import Path

from tempestweb.pwa import (
    ManifestOptions,
    emit_icons,
    validate_installable,
    write_manifest,
)

#: App metadata for this demo.
OPTIONS: ManifestOptions = ManifestOptions(
    name="PWA WebPush Demo",
    short_name="WebPush",
    description="A tempestweb demo that shows PWA install and WebPush notifications.",
    start_url="/",
    scope="/",
    display="standalone",
    theme_color="#111827",
    background_color="#f9fafb",
    lang="pt-BR",
    categories=["utilities"],
)


def main(dest: Path | None = None) -> dict[str, list[str | Path]]:
    """Emit the manifest and icon set into ``dest``, then validate installability.

    Args:
        dest: Output root directory. Defaults to ``<repo_root>/build``.

    Returns:
        A dict with ``"manifest"`` (manifest path list) and ``"icons"`` (icon paths).
    """
    if dest is None:
        dest = Path(__file__).resolve().parents[2] / "build"

    # 1. Write manifest.webmanifest
    manifest_path = write_manifest(dest / "manifest.webmanifest", options=OPTIONS)

    # 2. Emit icon set
    icon_paths = emit_icons(dest / "icons")

    # 3. Validate installability (must return [])
    manifest_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_installable(manifest_dict)

    print(f"manifest  -> {manifest_path}")
    print(f"icons     -> {len(icon_paths)} files under {dest / 'icons'}")
    print(f"installable? {errors if errors else '✓ yes (no errors)'}")

    return {
        "manifest": [manifest_path],
        "icons": icon_paths,
    }


if __name__ == "__main__":
    main()
```

Run it like this:

```bash
python examples/pwa-webpush/build_pwa.py
```

Expected output:

```
manifest  -> /path/to/build/manifest.webmanifest
icons     -> 5 files under /path/to/build/icons
installable? ✓ yes (no errors)
```

!!! info "What does `validate_installable` check?"
    The Chromium/Lighthouse install criteria for a PWA:

    - `name` **or** `short_name` filled in
    - `start_url` filled in
    - `display` is one of `{"standalone", "fullscreen", "minimal-ui"}`
    - A 192×192 PNG icon present
    - A 512×512 PNG icon present
    - At least one icon with `purpose` containing `"any"`

    An empty list (`[]`) means the app is ready to install.

### `ManifestOptions` fields

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Full application name |
| `short_name` | `str` | Home-screen label |
| `description` | `str` | Human description |
| `start_url` | `str` | URL opened on launch |
| `scope` | `str` | Navigation scope |
| `display` | `str` | Display mode (`"standalone"`, `"fullscreen"`, `"minimal-ui"`) |
| `theme_color` | `str` | Toolbar colour (CSS colour) |
| `background_color` | `str` | Splash background (CSS colour) |
| `lang` | `str` | BCP-47 language tag |
| `categories` | `list[str]` | App-store categories |
| `icons` | `list[dict]` | Overrides `DEFAULT_ICONS` when provided |
| `shortcuts` | `list[dict]` | P5 app shortcuts (advanced) |
| `share_target` | `dict \| None` | P5 share target descriptor |
| `file_handlers` | `list[dict]` | P5 file handler descriptors |

---

## The complete app

Here is the full `app.py`, ready to copy:

```python
"""PWA install + WebPush demo — exercises notification permission + subscription.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

This example demonstrates the PWA/WebPush flow:

1. The user presses **Enable notifications** — the app calls
   :func:`~tempestweb.native.notifications.request_permission` and stores the
   resulting :class:`~tempestweb.native.notifications.NotificationPermission`.
2. If permission is *granted*, the button changes to **Subscribe to push** —
   pressing it calls :func:`~tempestweb.native.notifications.subscribe` with the
   injected VAPID public key and stores the raw subscription dict returned by the
   browser.
3. The current status (idle / requesting / subscribing / subscribed / denied) is
   rendered in a :class:`~tempestweb._core.widgets.Text` feedback label so the user
   always sees what happened.

State machine
-------------
* ``Phase.IDLE``         — initial; the user has not interacted yet.
* ``Phase.REQUESTING``   — :func:`request_permission` is in flight.
* ``Phase.DENIED``       — the user blocked notifications.
* ``Phase.GRANTED``      — permission granted; subscription not yet requested.
* ``Phase.SUBSCRIBING``  — :func:`subscribe` is in flight.
* ``Phase.SUBSCRIBED``   — fully subscribed; ``subscription`` dict is populated.
* ``Phase.ERROR``        — unexpected error; ``error`` field has the message.

Dependency injection
--------------------
Both async callables (``request_permission`` and ``subscribe``) are injected
into ``State`` so :func:`build` is deterministic with *no bridge installed*.
The initial mount only reads ``app.state`` — the callables are never invoked
until the user presses a button.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import notifications
from tempestweb.native.notifications import NotificationPermission

#: Default VAPID public key used when none is injected (placeholder only;
#: a real app replaces this with its own server key).
DEMO_VAPID_KEY: str = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuB"
    "kr3qBUYIHBQFLXYp5Nksh8U"
)

# ---------------------------------------------------------------------------
# Injected callable types
# ---------------------------------------------------------------------------

#: Signature of the injected permission-request coroutine.
PermissionRequester = Callable[[], Awaitable[NotificationPermission]]

#: Signature of the injected subscribe coroutine.
Subscriber = Callable[[str], Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phases of the PWA WebPush consent flow.

    Attributes:
        IDLE: No user action yet.
        REQUESTING: Awaiting the browser permission prompt.
        DENIED: The user denied notification permission.
        GRANTED: Permission granted; WebPush subscription not yet requested.
        SUBSCRIBING: Awaiting the browser push subscription creation.
        SUBSCRIBED: Fully subscribed; ``subscription`` dict is available.
        ERROR: An unexpected error occurred.
    """

    IDLE = "idle"
    REQUESTING = "requesting"
    DENIED = "denied"
    GRANTED = "granted"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    """Top-level state for the PWA WebPush demo app.

    Attributes:
        phase: Current lifecycle phase.
        subscription: The raw push subscription dict once subscribed.
        error: Human-readable error message, populated in ``Phase.ERROR``.
        vapid_key: VAPID public key passed to :func:`subscribe`.
        request_permission: Injected coroutine for the permission request.
        subscribe: Injected coroutine for the push subscription.
    """

    phase: Phase = Phase.IDLE
    subscription: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    vapid_key: str = DEMO_VAPID_KEY
    request_permission: PermissionRequester = notifications.request_permission
    subscribe: Subscriber = notifications.subscribe


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_state() -> State:
    """Build the initial idle state with real capability defaults.

    Returns:
        A fresh :class:`State` in the ``IDLE`` phase.
    """
    return State()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[State]) -> Widget:
    """Render the PWA/WebPush consent UI from the current state.

    The view is a single :class:`~tempestweb._core.widgets.Column` containing:

    * A title.
    * A status feedback text that reflects the current phase.
    * A primary action button (changes label and handler per phase).
    * A subscription details section once fully subscribed.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def handle_request_permission() -> None:
        """Ask the browser for notification permission and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.REQUESTING))
        try:
            perm = await app.state.request_permission()
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        if perm is NotificationPermission.GRANTED:
            app.set_state(lambda s: setattr(s, "phase", Phase.GRANTED))
        elif perm is NotificationPermission.DENIED:
            app.set_state(lambda s: setattr(s, "phase", Phase.DENIED))
        else:
            # DEFAULT — the user dismissed the prompt; stay at IDLE
            app.set_state(lambda s: setattr(s, "phase", Phase.IDLE))

    async def handle_subscribe() -> None:
        """Subscribe to WebPush using the stored VAPID key and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.SUBSCRIBING))
        try:
            sub = await app.state.subscribe(app.state.vapid_key)
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_subscribed(s: State) -> None:
            s.phase = Phase.SUBSCRIBED
            s.subscription = sub

        app.set_state(on_subscribed)

    def handle_reset() -> None:
        """Reset state back to IDLE."""

        def reset(s: State) -> None:
            s.phase = Phase.IDLE
            s.subscription = {}
            s.error = ""

        app.set_state(reset)

    # ------------------------------------------------------------------
    # Status label
    # ------------------------------------------------------------------

    phase = app.state.phase

    status_messages: dict[Phase, str] = {
        Phase.IDLE: "Notifications are not yet enabled.",
        Phase.REQUESTING: "Waiting for browser permission…",
        Phase.DENIED: (
            "Permission denied. You can re-enable notifications"
            " in your browser settings."
        ),
        Phase.GRANTED: (
            "Permission granted. You can now subscribe to push notifications."
        ),
        Phase.SUBSCRIBING: "Creating push subscription…",
        Phase.SUBSCRIBED: "Successfully subscribed to push notifications!",
        Phase.ERROR: f"Error: {app.state.error}",
    }

    status_text: Widget = Text(
        content=status_messages[phase],
        key="status-text",
    )

    # ------------------------------------------------------------------
    # Primary action button
    # ------------------------------------------------------------------

    children: list[Widget] = [
        Text(
            content="PWA WebPush Demo",
            style=Style(font_size=22.0),
            key="title",
        ),
        Text(
            content="Enable browser push notifications to receive real-time updates.",
            style=Style(font_size=14.0),
            key="subtitle",
        ),
        status_text,
    ]

    if phase is Phase.REQUESTING or phase is Phase.SUBSCRIBING:
        children.append(
            Row(
                style=Style(gap=8.0),
                children=[
                    Spinner(key="loading-spinner"),
                    Text(
                        content=(
                            "Requesting permission…"
                            if phase is Phase.REQUESTING
                            else "Subscribing…"
                        ),
                        key="loading-label",
                    ),
                ],
                key="loading-row",
            )
        )
    elif phase is Phase.IDLE or phase is Phase.DENIED:
        children.append(
            Button(
                label="Enable notifications",
                on_click=handle_request_permission,
                key="btn-enable",
            )
        )
        if phase is Phase.DENIED:
            children.append(
                Button(
                    label="Try again",
                    on_click=handle_request_permission,
                    key="btn-retry",
                )
            )
    elif phase is Phase.GRANTED:
        children.append(
            Button(
                label="Subscribe to push",
                on_click=handle_subscribe,
                key="btn-subscribe",
            )
        )
    elif phase is Phase.SUBSCRIBED:
        endpoint = app.state.subscription.get("endpoint", "")
        children.append(
            Column(
                style=Style(gap=4.0, padding=Edge.all(12.0)),
                children=[
                    Text(content="Subscription endpoint:", key="sub-label"),
                    Text(
                        content=endpoint[:64] + "…" if len(endpoint) > 64 else endpoint,
                        key="sub-endpoint",
                    ),
                ],
                key="sub-details",
            )
        )
        children.append(
            Button(
                label="Reset",
                on_click=handle_reset,
                key="btn-reset",
            )
        )
    elif phase is Phase.ERROR:
        children.append(
            Button(
                label="Try again",
                on_click=handle_reset,
                key="btn-error-reset",
            )
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/pwa-webpush/app.py
```

Python runs **inside the browser** via Pyodide. The `request_permission` call goes
directly to `client/native/notifications.js` via FFI — no server, no extra network
hop.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/pwa-webpush/app.py
```

Python runs on the server. Each `await app.state.request_permission()` serialises a
`native_call` envelope, sends it over the WebSocket to the browser, waits for the
`native_result` response, and resumes the coroutine.

!!! check "Verification"
    In either mode you should see:

    1. Title "PWA WebPush Demo" and a descriptive subtitle
    2. Status label: "Notifications are not yet enabled."
    3. Button **Enable notifications**
    4. Click the button → label changes to "Waiting for browser permission…" + Spinner
    5. Grant permission in the browser prompt → button changes to **Subscribe to push**
    6. Click **Subscribe to push** → Spinner appears again
    7. After subscribing: "Subscription endpoint:" section and **Reset** button
    8. Click **Reset** → returns to the initial state

!!! warning "Warning — browser permission"
    The notification permission prompt only appears on pages served over
    **HTTPS** or **localhost**. With `tempestweb dev` locally, `localhost` works.
    In production you need HTTPS.

---

## How the native bridge works

The diagram below shows the path of a `request_permission` call in **Mode B**
(server):

```
Python view()
    │
    ├─ await app.state.request_permission()
    │       │
    │       ▼
    │  send_native_call("notifications.request_permission", {})
    │       │
    │       ▼
    │  ProxyBridge.call(envelope)  ── native_call ──► browser (WS)
    │       │                                              │
    │       │                           client/native/notifications.js
    │       │                           Notification.requestPermission()
    │       │                                              │
    │       │◄────────── native_result ◄──────────────────┘
    │       │
    │  resolve_native_result(call_id, payload)
    │       │
    └─ NotificationPermission.GRANTED / DENIED / DEFAULT
```

In **Mode A** (WASM), the same Python call goes straight to JavaScript via Pyodide
FFI — no network round-trip at all.

!!! info "Note — `install_bridge` / `uninstall_bridge`"
    The runtime bootstrap (Mode A or B) calls `install_bridge(bridge)` once. In
    tests, you do the same with a `_FakeBridge` and call `uninstall_bridge()` in
    teardown to guarantee isolation between tests.

---

## Generating the PWA artifacts

### Running the build script

```bash
python examples/pwa-webpush/build_pwa.py
```

This creates under `build/`:

```
build/
├── manifest.webmanifest
└── icons/
    ├── icon-192.png
    ├── icon-512.png
    ├── maskable-192.png
    ├── maskable-512.png
    └── apple-touch-icon.png
```

### Validating installability directly

```python
import json
from pathlib import Path
from tempestweb.pwa import validate_installable

manifest = json.loads(Path("build/manifest.webmanifest").read_text())
errors = validate_installable(manifest)
print(errors)  # [] means installable
```

### Using it from another script

`build_pwa.main(dest)` is importable — you can point `dest` at a pytest
`tmp_path` or a custom deploy directory:

```python
from pathlib import Path
from examples.pwa_webpush import build_pwa

result = build_pwa.main(Path("/my/deploy/dir"))
print(result["manifest"])  # [Path('/my/deploy/dir/manifest.webmanifest')]
print(len(result["icons"]))  # 5
```

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

# Tests (10 green tests, Groups A and B)
pytest -q tests/unit/test_example_pwa_webpush.py
```

The 10 tests cover:

| Group | Test | What it verifies |
|---|---|---|
| A | `test_initial_build_requires_no_bridge` | Initial render does not invoke the bridge |
| A | `test_request_permission_granted_transitions_to_granted` | `IDLE → GRANTED` + subscribe button appears |
| A | `test_request_permission_denied_transitions_to_denied` | `IDLE → DENIED` + enable and retry buttons |
| A | `test_subscribe_transitions_to_subscribed` | `GRANTED → SUBSCRIBED` + endpoint displayed |
| A | `test_reset_returns_to_idle` | `SUBSCRIBED → IDLE` + state cleared |
| A | `test_permission_error_transitions_to_error` | Exception → `ERROR` + try-again button |
| B | `test_build_pwa_main_produces_installable_manifest` | `validate_installable` returns `[]` |
| B | `test_build_pwa_main_writes_icon_files` | 5 valid PNGs written |
| B | `test_build_pwa_manifest_fields` | `name`, `short_name`, `display` fields correct |
| B | `test_build_pwa_validate_installable_direct` | `build_manifest(OPTIONS)` is installable |

---

## How it works under the hood

### The async update cycle

```
Button click
      │
      ▼
async handler (e.g. handle_request_permission)
      │
      ├─ app.set_state(phase = REQUESTING)   ← immediate render with Spinner
      │
      ▼
await app.state.request_permission()         ← bridge resolves via FFI (A) or WS (B)
      │
      ▼
app.set_state(phase = GRANTED / DENIED / IDLE / ERROR)
      │
      ▼
view(app) called again → new widget tree
      │
      ▼
reconciler computes diff (patches)
      │
      ▼
DOM updated (minimum changes)
```

### Why inject callables into state?

If `request_permission` and `subscribe` were direct calls to the `notifications`
module, testing `view` would require a real bridge to be installed. With injection,
you simply write:

```python
app.state.request_permission = lambda: NotificationPermission.GRANTED
```

and the handler works identically — no bridge setup, no global side effects.

### Icons without Pillow

`emit_icons` generates 8-bit RGBA PNGs using only `struct` and `zlib` from the
standard library. Each maskable icon gets a ~10% safe-zone inset so the OS mask
never clips the artwork. The result is accepted by browsers and by Lighthouse.

---

## Recap

In this tutorial you learned:

- ✅ Model a **consent flow** as an explicit state machine with `StrEnum`
- ✅ Inject async callables into state for **deterministic testing** without a bridge
- ✅ Use "loading" phases (`REQUESTING`, `SUBSCRIBING`) for immediate visual feedback
- ✅ Call `tempestweb.native.notifications.request_permission` and `subscribe` from Python
- ✅ Generate and validate an installable `manifest.webmanifest` with `write_manifest` and `validate_installable`
- ✅ Emit valid PNG icons without external dependencies using `emit_icons`
- ✅ Run the same app in **both modes** without changing a single line of `view`

---

## Next steps

- 💡 Add a **server-side WebPush sender** using `tempestweb.server.webpush.WebPushService`
  with your own VAPID key generated by `py-vapid`
- 💡 Persist the `subscription` in `localStorage` via `tempestweb.native.storage.put` to
  avoid re-subscribing on every visit
- 💡 Explore the [PWA documentation](../pwa.en.md) for the Service Worker (P1) and
  offline-first mode (P2)
- 💡 Read the [notification-center example](notification-center.en.md) to see how to
  display local notifications with `tempestweb.native.notifications.notify`
