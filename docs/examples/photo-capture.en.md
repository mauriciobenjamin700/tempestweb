# Camera Photo Capture 📸

Build an app that accesses the device camera, shows a spinner while capturing, and displays a photo preview with metadata — all written in pure Python.

---

## What you'll build

A camera capture app with a complete lifecycle:

- 🟢 **IDLE state** — "Capture" button visible, ready to fire
- ⏳ **CAPTURING state** — spinner + "Accessing camera…" text while the browser captures the frame
- 🖼 **CAPTURED state** — photo preview as a `data:` URI inside a `Card`, with format, width, and height badges
- ❌ **ERROR state** — friendly error message when the user denies camera permission, with a "Try again" button

!!! note "Note — native capability N4"
    The camera is always accessed **in the browser**, never on the server. In Mode A (WASM) Python calls `navigator.mediaDevices` via FFI; in Mode B (server) Python sends a `native_call` over the WebSocket and the JS client executes the same call, returning the photo as a `native_result`. Your `view` function is identical in both modes.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server
- [Native capabilities](../capabilities.md) — the bridge model

---

## Creating the project

Create the folder and app file:

```bash
mkdir -p examples/photo-capture
touch examples/photo-capture/app.py
```

---

## Step 1 — Understanding the lifecycle

Before writing code, think about the **four possible UI states**:

| Phase | What the user sees |
|---|---|
| `IDLE` | Title + subtitle + "Capture" button |
| `CAPTURING` | Title + spinner + "Accessing camera…" text |
| `CAPTURED` | Title + card with photo + metadata badges + "Capture" and "Clear" buttons |
| `ERROR` | Title + error card + "Try again" button |

This diagram summarises the transitions:

```
IDLE ──(click Capture)──► CAPTURING
                               │
              ┌────────────────┴────────────────┐
              ▼ (photo returned)                 ▼ (NativeError)
           CAPTURED                            ERROR
              │                                  │
       (click Clear)                     (click Try again)
              │                                  │
              └──────────────► IDLE ◄────────────┘
```

---

## Step 2 — The phase enumeration

Use `StrEnum` so phases are readable in logs and on the wire:

```python
from enum import StrEnum


class Phase(StrEnum):
    """Lifecycle phase of the camera capture flow.

    Attributes:
        IDLE: Nothing has been captured yet — the *Capture* button is shown.
        CAPTURING: A capture is in flight — the spinner is shown.
        CAPTURED: A photo was returned — the preview card is shown.
        ERROR: The capture failed — a brief error message is shown.
    """

    IDLE = "idle"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    ERROR = "error"
```

!!! tip "Tip — `StrEnum` vs `str`"
    `Phase.IDLE == "idle"` evaluates as `True`, so you can compare with `is` (enum identity) **or** `==` (string value). The app uses `is` to be explicit.

---

## Step 3 — The `Photo` type and the `Capturer` alias

`tempestweb.native.camera.Photo` is a **frozen** (immutable) Pydantic model returned by the bridge after capturing:

```python
from tempestweb.native.camera import Photo
```

| Field | Type | Description |
|---|---|---|
| `mime_type` | `str` | e.g. `"image/jpeg"`, `"image/png"` |
| `width` | `int` | Frame width in pixels |
| `height` | `int` | Frame height in pixels |
| `data_base64` | `str` | Image bytes encoded as base64 |

`photo.to_bytes()` decodes `data_base64` to `bytes` — useful for uploading via `native.http`.

The `Capturer` alias names the type of the injectable callable stored in state:

```python
from collections.abc import Awaitable, Callable

Capturer = Callable[[], Awaitable[Photo]]
```

---

## Step 4 — State and the default capture callable

```python
from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb.native import NativeError
from tempestweb.native import camera as _camera
from tempestweb.native.camera import Photo

Capturer = Callable[[], Awaitable[Photo]]


async def _default_capture() -> Photo:
    """Capture a rear-facing JPEG at 85 % quality.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the user denies permission, no camera is available, or
            the page is not in a secure context.
        BrowserUnavailableError: If no native bridge is installed.
    """
    return await _camera.capture(facing="environment", quality=0.85)


@dataclass
class PhotoState:
    """State for the camera-capture app.

    Attributes:
        phase: The current lifecycle phase.
        photo: The most-recently captured photo, or ``None`` before the first
            successful capture.
        error: The error message surfaced when ``phase`` is ``ERROR``.
        capture: The injected coroutine factory that performs the capture;
            defaults to ``native.camera.capture`` so the app works
            out-of-the-box in both modes.
    """

    phase: Phase = Phase.IDLE
    photo: Photo | None = None
    error: str = ""
    capture: Capturer = field(default=_default_capture)


def make_state() -> PhotoState:
    """Build the initial, idle camera-capture state.

    Returns:
        A fresh :class:`PhotoState` in the ``IDLE`` phase.
    """
    return PhotoState()
```

!!! info "Why does `capture` live in the state?"
    Injecting the capture callable directly into `PhotoState` is tempestweb's **dependency injection** pattern: in production the field uses `_default_capture` (which calls the real camera); in tests you pass a fake callable — no monkey-patching, no global mock, no real bridge needed. See the [testing section](#testing-without-a-camera) below.

---

## Step 5 — The `_data_uri` helper

To display the photo as an `<img>`, we need a `data:` URI:

```python
import base64


def _data_uri(photo: Photo) -> str:
    """Build a browser-safe ``data:`` URI from a :class:`Photo`.

    Args:
        photo: The captured photo with base64-encoded bytes.

    Returns:
        A ``data:<mime_type>;base64,<data_base64>`` string suitable for use as
        an ``<img src>`` attribute.
    """
    try:
        base64.b64decode(photo.data_base64, validate=True)
    except Exception:
        return ""
    return f"data:{photo.mime_type};base64,{photo.data_base64}"
```

!!! tip "Tip — defensive validation"
    Before building the URI, `b64decode(..., validate=True)` checks the payload is valid base64. If the bridge or a test sends corrupt bytes, `_data_uri` returns `""` instead of producing a broken URI in the DOM. The `view` handles this by showing a text placeholder.

---

## Step 6 — The async event handlers

Handlers live **inside `view()`**, capturing `app` by closure. This is intentional — each render creates fresh closures bound to the current state.

### `do_capture` handler (async)

```python
async def do_capture() -> None:
    """Drive the async capture flow through all lifecycle phases."""
    app.set_state(lambda s: setattr(s, "phase", Phase.CAPTURING))
    try:
        photo: Photo = await app.state.capture()
    except NativeError as exc:
        msg = str(exc)

        def _on_native_error(s: PhotoState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_native_error)
        return
    except Exception as exc:
        message = str(exc)

        def _on_error(s: PhotoState) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(_on_error)
        return

    def _on_success(s: PhotoState) -> None:
        s.phase = Phase.CAPTURED
        s.photo = photo

    app.set_state(_on_success)
```

Notice the **three explicit state transitions**:

1. `IDLE → CAPTURING` — immediately on entering the handler.
2. `CAPTURING → ERROR` — if `NativeError` (permission denied, camera unavailable) or any unexpected exception.
3. `CAPTURING → CAPTURED` — after the photo is returned successfully.

!!! warning "Catching `NativeError` separately"
    `NativeError` carries a machine-readable `code` (`"permission_denied"`, `"unavailable"`, `"insecure_context"`). Catching it **before** the generic `Exception` ensures you can, in the future, show per-code messages without changing the handler structure.

### `reset` handler (sync)

```python
def reset() -> None:
    """Reset the state back to the idle phase so the user can capture again."""

    def _do_reset(s: PhotoState) -> None:
        s.phase = Phase.IDLE
        s.photo = None
        s.error = ""

    app.set_state(_do_reset)
```

---

## Step 7 — Building the widget tree per phase

The `view` function is a **pure, I/O-free** transformation of `PhotoState` → widget tree. All branching lives in an `if/elif/else` on `app.state.phase`.

### IDLE phase

```python
header = Text(
    content="Camera Capture",
    style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
    key="title",
)
subtitle = Text(
    content="Tap the button below to capture a photo from your device camera.",
    style=Style(font_size=14.0),
    key="subtitle",
)
capture_btn = Button(label="Capture", on_click=do_capture, key="capture")

if app.state.phase is Phase.IDLE:
    body_children = [header, subtitle, capture_btn]
```

### CAPTURING phase

```python
elif app.state.phase is Phase.CAPTURING:
    body_children = [
        header,
        Spinner(key="spinner"),
        Text(content="Accessing camera…", style=Style(font_size=14.0), key="wait"),
    ]
```

!!! note "`Spinner` — immediate visual feedback"
    `Spinner` needs no parameters beyond a `key`. The reconciler swaps the button for the spinner in a single patch — the user sees the transition immediately.

### ERROR phase

```python
elif app.state.phase is Phase.ERROR:
    body_children = [
        header,
        Card(
            key="error-card",
            children=[
                Text(
                    content="Camera unavailable",
                    style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
                    key="err-title",
                ),
                Text(
                    content=app.state.error,
                    style=Style(font_size=13.0),
                    key="err-msg",
                ),
            ],
        ),
        Button(label="Try again", on_click=do_capture, key="retry"),
    ]
```

### CAPTURED phase

This is the richest phase: photo preview + metadata badges.

```python
else:  # CAPTURED
    photo = app.state.photo
    assert photo is not None, "phase is CAPTURED but photo is None"

    data_uri = _data_uri(photo)
    image_widget: Widget
    if data_uri:
        image_widget = Image(
            src=data_uri,
            fit=ImageFit.COVER,
            alt="Captured photo",
            key="preview-img",
            style=Style(width=320.0, height=240.0, radius=8.0),
        )
    else:
        image_widget = Text(
            content="(image preview unavailable)",
            style=Style(font_size=12.0),
            key="preview-placeholder",
        )

    meta_row: list[Widget] = [
        _meta_badge("Format", photo.mime_type, "badge-mime"),
        _meta_badge("Width", f"{photo.width} px", "badge-width"),
        _meta_badge("Height", f"{photo.height} px", "badge-height"),
    ]

    body_children = [
        header,
        Card(
            key="photo-card",
            children=[
                image_widget,
                Divider(key="divider"),
                Row(
                    style=Style(
                        gap=8.0,
                        justify=JustifyContent.START,
                        align=AlignItems.CENTER,
                    ),
                    children=meta_row,
                    key="meta-row",
                ),
            ],
        ),
        Row(
            style=Style(gap=8.0, justify=JustifyContent.CENTER),
            children=[
                capture_btn,
                Button(label="Clear", on_click=reset, key="clear"),
            ],
            key="actions",
        ),
    ]
```

### Root of the tree

```python
return Column(
    style=Style(gap=16.0, padding=Edge.all(20.0)),
    children=body_children,
)
```

---

## Step 8 — The `_meta_badge` helper

Each metadata badge is a small `Card` with two stacked `Text` widgets:

```python
def _meta_badge(label: str, value: str, key: str) -> Widget:
    """Build a small metadata badge widget.

    Args:
        label: The badge label (e.g. ``"Format"``).
        value: The badge value (e.g. ``"image/jpeg"``).
        key: The widget key for reconciliation.

    Returns:
        A :class:`~tempest_core.components.Card` containing a label/value
        column.
    """
    return Card(
        key=key,
        style=Style(padding=Edge.symmetric(vertical=6.0, horizontal=10.0)),
        children=[
            Text(
                content=label,
                style=Style(font_size=10.0, font_weight=FontWeight.BOLD),
                key=f"{key}-label",
            ),
            Text(
                content=value,
                style=Style(font_size=12.0),
                key=f"{key}-value",
            ),
        ],
    )
```

---

## The complete app

Here is the full `examples/photo-capture/app.py`, ready to copy:

```python
"""Camera capture view — exercises ``native.camera.capture()`` (N4).

Like :mod:`examples.fetch.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates an async native-capability handler: pressing *Capture* runs an
``async`` handler that:

1. Flips the view into a ``CAPTURING`` loading state (showing a
   :class:`~tempest_core.widgets.Spinner`).
2. Awaits the injected ``capture`` callable (defaults to
   ``native.camera.capture``), which resolves to a :class:`~tempestweb.native.Photo`
   carrying the MIME type, pixel dimensions, and base64-encoded bytes.
3. Renders the result in a :class:`~tempest_core.components.Card` with a
   data-URI :class:`~tempest_core.widgets.Image` preview and metadata row.

If the user denies camera permission, the bridge raises a
:class:`~tempestweb.native.NativeError` — the handler catches it and surfaces a
tidy error message rather than crashing the view.

The ``capture`` callable is **dependency-injected** into :class:`PhotoState`, so
the view is fully deterministic under test (no real bridge needed; a fake bridge
can also be installed for integration tests). The initial render never calls the
capability.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.components import Card, Divider
from tempest_core.style import AlignItems, Edge, FontWeight, JustifyContent
from tempest_core.widgets import Button, Column, Image, ImageFit, Row, Spinner, Text
from tempestweb.native import NativeError
from tempestweb.native import camera as _camera
from tempestweb.native.camera import Photo

# ---------------------------------------------------------------------------
# Type alias for the injected capture callable.
# ---------------------------------------------------------------------------

#: A coroutine factory that captures a single photo.  Injected into state so
#: the example stays deterministic under test; in a real app the default is
#: ``native.camera.capture``.
Capturer = Callable[[], Awaitable[Photo]]


# ---------------------------------------------------------------------------
# Phase enumeration
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phase of the camera capture flow.

    Attributes:
        IDLE: Nothing has been captured yet — the *Capture* button is shown.
        CAPTURING: A capture is in flight — the spinner is shown.
        CAPTURED: A photo was returned — the preview card is shown.
        ERROR: The capture failed — a brief error message is shown.
    """

    IDLE = "idle"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Default capture callable (wraps the real native capability)
# ---------------------------------------------------------------------------


async def _default_capture() -> Photo:
    """Capture a rear-facing JPEG at 85 % quality.

    This is the production default injected into :class:`PhotoState`. It is
    never called during testing (the fake bridge or a mock callable is
    injected instead), but it **is** called in live deployments — the
    docstring preserves the intent for readers.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the user denies permission, no camera is available, or
            the page is not in a secure context.
        BrowserUnavailableError: If no native bridge is installed (Mode A
            requires the FFI bridge; Mode B requires the proxy bridge).
    """
    return await _camera.capture(facing="environment", quality=0.85)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class PhotoState:
    """State for the camera-capture app.

    Attributes:
        phase: The current lifecycle phase.
        photo: The most-recently captured photo, or ``None`` before the first
            successful capture.
        error: The error message surfaced when ``phase`` is ``ERROR``.
        capture: The injected coroutine factory that performs the capture;
            defaults to ``native.camera.capture`` so the app works
            out-of-the-box in both modes.
    """

    phase: Phase = Phase.IDLE
    photo: Photo | None = None
    error: str = ""
    capture: Capturer = field(default=_default_capture)


def make_state() -> PhotoState:
    """Build the initial, idle camera-capture state.

    Returns:
        A fresh :class:`PhotoState` in the ``IDLE`` phase.
    """
    return PhotoState()


# ---------------------------------------------------------------------------
# Helper: build a data URI from a Photo
# ---------------------------------------------------------------------------


def _data_uri(photo: Photo) -> str:
    """Build a browser-safe ``data:`` URI from a :class:`Photo`.

    Args:
        photo: The captured photo with base64-encoded bytes.

    Returns:
        A ``data:<mime_type>;base64,<data_base64>`` string suitable for use as
        an ``<img src>`` attribute.
    """
    try:
        base64.b64decode(photo.data_base64, validate=True)
    except Exception:
        return ""
    return f"data:{photo.mime_type};base64,{photo.data_base64}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[PhotoState]) -> Widget:
    """Render the camera-capture UI from the current lifecycle phase.

    The view is a thin, stateless transformation of :class:`PhotoState` to a
    widget tree.  All state mutations happen inside the ``do_capture`` async
    handler — the view function itself never performs I/O.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state phase.
    """

    # ------------------------------------------------------------------
    # Async handler — IDLE → CAPTURING → CAPTURED | ERROR
    # ------------------------------------------------------------------

    async def do_capture() -> None:
        """Drive the async capture flow through all lifecycle phases."""
        app.set_state(lambda s: setattr(s, "phase", Phase.CAPTURING))
        try:
            photo: Photo = await app.state.capture()
        except NativeError as exc:
            msg = str(exc)

            def _on_native_error(s: PhotoState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_native_error)
            return
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            message = str(exc)

            def _on_error(s: PhotoState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(_on_error)
            return

        def _on_success(s: PhotoState) -> None:
            s.phase = Phase.CAPTURED
            s.photo = photo

        app.set_state(_on_success)

    # ------------------------------------------------------------------
    # Reset handler — go back to IDLE
    # ------------------------------------------------------------------

    def reset() -> None:
        """Reset the state back to the idle phase so the user can capture again."""

        def _do_reset(s: PhotoState) -> None:
            s.phase = Phase.IDLE
            s.photo = None
            s.error = ""

        app.set_state(_do_reset)

    # ------------------------------------------------------------------
    # Body widgets — vary by phase
    # ------------------------------------------------------------------

    header = Text(
        content="Camera Capture",
        style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        key="title",
    )
    subtitle = Text(
        content="Tap the button below to capture a photo from your device camera.",
        style=Style(font_size=14.0),
        key="subtitle",
    )
    capture_btn = Button(label="Capture", on_click=do_capture, key="capture")

    body_children: list[Widget]

    if app.state.phase is Phase.IDLE:
        body_children = [
            header,
            subtitle,
            capture_btn,
        ]

    elif app.state.phase is Phase.CAPTURING:
        body_children = [
            header,
            Spinner(key="spinner"),
            Text(content="Accessing camera…", style=Style(font_size=14.0), key="wait"),
        ]

    elif app.state.phase is Phase.ERROR:
        body_children = [
            header,
            Card(
                key="error-card",
                children=[
                    Text(
                        content="Camera unavailable",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                        key="err-title",
                    ),
                    Text(
                        content=app.state.error,
                        style=Style(font_size=13.0),
                        key="err-msg",
                    ),
                ],
            ),
            Button(label="Try again", on_click=do_capture, key="retry"),
        ]

    else:  # CAPTURED
        photo = app.state.photo
        assert photo is not None, "phase is CAPTURED but photo is None"

        data_uri = _data_uri(photo)
        image_widget: Widget
        if data_uri:
            image_widget = Image(
                src=data_uri,
                fit=ImageFit.COVER,
                alt="Captured photo",
                key="preview-img",
                style=Style(width=320.0, height=240.0, radius=8.0),
            )
        else:
            image_widget = Text(
                content="(image preview unavailable)",
                style=Style(font_size=12.0),
                key="preview-placeholder",
            )

        meta_row: list[Widget] = [
            _meta_badge("Format", photo.mime_type, "badge-mime"),
            _meta_badge("Width", f"{photo.width} px", "badge-width"),
            _meta_badge("Height", f"{photo.height} px", "badge-height"),
        ]

        body_children = [
            header,
            Card(
                key="photo-card",
                children=[
                    image_widget,
                    Divider(key="divider"),
                    Row(
                        style=Style(
                            gap=8.0,
                            justify=JustifyContent.START,
                            align=AlignItems.CENTER,
                        ),
                        children=meta_row,
                        key="meta-row",
                    ),
                ],
            ),
            Row(
                style=Style(gap=8.0, justify=JustifyContent.CENTER),
                children=[
                    capture_btn,
                    Button(label="Clear", on_click=reset, key="clear"),
                ],
                key="actions",
            ),
        ]

    return Column(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=body_children,
    )


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _meta_badge(label: str, value: str, key: str) -> Widget:
    """Build a small metadata badge widget.

    Args:
        label: The badge label (e.g. ``"Format"``).
        value: The badge value (e.g. ``"image/jpeg"``).
        key: The widget key for reconciliation.

    Returns:
        A :class:`~tempest_core.components.Card` containing a label/value
        column.
    """
    return Card(
        key=key,
        style=Style(padding=Edge.symmetric(vertical=6.0, horizontal=10.0)),
        children=[
            Text(
                content=label,
                style=Style(font_size=10.0, font_weight=FontWeight.BOLD),
                key=f"{key}-label",
            ),
            Text(
                content=value,
                style=Style(font_size=12.0),
                key=f"{key}-value",
            ),
        ],
    )
```

---

## Running the example ▶

!!! warning "Native capabilities require a bridge"
    `native.camera.capture` needs a **bridge** installed to work. Without a bridge, any capability call raises `BrowserUnavailableError` immediately.

    - **Mode A (WASM):** the runtime installs an `FFIBridge` automatically when loading Pyodide in the browser. You don't need to do anything beyond running the dev server.
    - **Mode B (server):** each WebSocket session creates and installs a `ProxyBridge` automatically. The server sends a `native_call` to the client; the JS client runs `navigator.mediaDevices.getUserMedia`, captures the frame, and returns via `native_result`.
    - **Outside the browser** (plain Python process, server without an active session): no bridge is installed → any capability call fails with `BrowserUnavailableError`. This is the correct behaviour — use a fake in tests (see below).

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/photo-capture
```

Python runs **inside the browser** via Pyodide. The camera is accessed directly through `navigator.mediaDevices` via FFI, without a network round-trip.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/photo-capture
```

Python runs on the server; the `ProxyBridge` serialises the `native_call` and sends it to the client over the WebSocket. The JS client captures the photo and returns the `native_result` with the base64 bytes. The server deserialises it, creates the `Photo`, and continues the handler.

!!! check "Verification"
    In either mode, you should see:

    1. Title "Camera Capture" + subtitle + **Capture** button
    2. Click **Capture** → spinner appears immediately (CAPTURING phase)
    3. Grant camera permission in the browser → card with preview appears (CAPTURED phase)
    4. Badges display the format (`image/jpeg`), width, and height in pixels
    5. Click **Clear** → returns to the IDLE state
    6. Click **Capture** and **deny** permission → error card with message (ERROR phase)
    7. Click **Try again** → starts a new capture attempt

---

## Testing without a camera

One of the strengths of this example's design is that you can test **every lifecycle path without a real camera** and without installing any bridge.

### Option 1 — Injecting a fake callable

The simplest approach: pass a custom `capture` when creating `PhotoState`.

```python
import asyncio
import base64
import pytest
from examples_photo_capture import make_state, view, Phase
from tempest_core import App, build
from tempestweb.native.camera import Photo

_FAKE_B64 = base64.b64encode(b"fake-image-bytes").decode()
_FAKE_PHOTO = Photo(
    mime_type="image/png", width=640, height=480, data_base64=_FAKE_B64
)

async def fake_capture() -> Photo:
    return _FAKE_PHOTO

def test_success_path() -> None:
    state = make_state()
    state.capture = fake_capture  # direct injection

    app = App(state=state, view=view, apply_patches=lambda _: None)
    asyncio.run(view(app).on_click())  # locate and fire the handler
    assert app.state.phase is Phase.CAPTURED
    assert app.state.photo.width == 640
```

### Option 2 — Installing a `FakeBridge` (integration)

For integration tests that exercise the full path `native.camera.capture → send_native_call → bridge.call`, install a fake bridge with `install_bridge`/`uninstall_bridge`:

```python
from typing import Any
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.camera import Photo
import base64

_PNG_1X1_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


class FakeBridge:
    """Scripted FFI bridge — returns a fixed 640x480 PNG photo."""

    def __init__(self, *, fail: bool = False) -> None:
        self.last_envelope: dict[str, Any] | None = None
        self._fail = fail

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.last_envelope = envelope
        if self._fail and envelope.get("capability") == "camera.capture":
            return {"ok": False, "error": "permission_denied", "message": "Camera denied"}
        if envelope.get("capability") == "camera.capture":
            return {
                "ok": True,
                "value": {
                    "mime_type": "image/png",
                    "width": 640,
                    "height": 480,
                    "data_base64": _PNG_1X1_B64,
                },
            }
        return {"ok": False, "error": "unavailable", "message": "no handler"}


import pytest

@pytest.fixture(autouse=True)
def _clean_bridge():
    uninstall_bridge()
    yield
    uninstall_bridge()

@pytest.fixture()
def fake_bridge():
    bridge = FakeBridge()
    install_bridge(bridge)
    return bridge

@pytest.fixture()
def failing_bridge():
    bridge = FakeBridge(fail=True)
    install_bridge(bridge)
    return bridge
```

!!! info "Why `autouse=True` on `_clean_bridge`?"
    It guarantees no bridge "leaks" between tests. Even if a test fails abruptly mid-way, the `yield` in the fixture ensures `uninstall_bridge()` is called during teardown.

### The 6 tests in the official suite

The suite in `tests/unit/test_example_photo_capture.py` covers:

| Test | What it verifies |
|---|---|
| `test_build_without_bridge_yields_idle_tree` | `build(view(app))` works with no bridge installed (initial render is pure) |
| `test_idle_state_has_capture_button` | IDLE phase contains a widget with `key="capture"` |
| `test_capture_handler_transitions_to_captured` | `do_capture()` with an OK bridge → CAPTURED phase, `photo.width == 640` |
| `test_capture_handler_surfaces_permission_error` | `do_capture()` with `fail=True` bridge → ERROR phase, `error` contains `"permission_denied"` |
| `test_photo_to_bytes_round_trips` | `Photo.to_bytes()` decodes base64 correctly |
| `test_photo_is_frozen_after_construction` | `Photo` is immutable (Pydantic frozen model) |

---

## Automated verification ✅

Run the full checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests (includes all 6 photo-capture tests)
pytest -q
```

All should pass green. The example was designed to be `mypy --strict` clean — every variable, parameter, and return type is explicitly annotated.

---

## How it works under the hood

### The async update cycle

```
Click "Capture" button
      │
      ▼
do_capture() (async handler)
      │
      ├─► app.set_state(phase = CAPTURING)  ←── re-render: spinner appears
      │
      ▼
await app.state.capture()
      │
      ├── Mode A: FFIBridge.call(envelope)
      │     └─► window.__tempestweb_native__(envelope) [JS, in-process]
      │             └─► navigator.mediaDevices.getUserMedia(...)
      │
      └── Mode B: ProxyBridge.call(envelope)
            └─► sends native_call over WebSocket
                    └─► client/native/camera.js
                            └─► navigator.mediaDevices.getUserMedia(...)
                    └─► receives native_result over WebSocket
      │
      ├── NativeError? ──► app.set_state(phase = ERROR)    ←── re-render: error card
      └── OK           ──► app.set_state(phase = CAPTURED) ←── re-render: photo card
```

### Why does the initial render not need a bridge?

`view(app)` only **reads** `app.state` and builds widgets — it never calls capabilities. `do_capture` is only executed when the user **clicks** the button, long after the initial render. That is why `build(view(app))` works in any Python context, without a browser, without a bridge.

### `ImageFit.COVER` — how the photo is fitted

`Image(fit=ImageFit.COVER, ...)` instructs the renderer to cover the container (`320 × 240`) by cropping the edges if necessary — the same behaviour as `object-fit: cover` in CSS. This ensures the preview always has fixed dimensions, regardless of the actual size of the captured photo.

### `Divider` — semantic separation

`Divider` is a child-free component that the renderer translates into an `<hr>`. Used between the photo preview and the metadata badges to create visual separation without extra `padding`.

---

## Recap

In this tutorial you learned:

- ✅ Model an **async lifecycle** with `StrEnum` (IDLE → CAPTURING → CAPTURED | ERROR)
- ✅ Use **dependency injection** in state to keep `view` testable without a real camera
- ✅ Write an `async` handler that performs **multiple sequential state transitions**
- ✅ Catch `NativeError` separately to handle denied permissions gracefully
- ✅ Build an image preview with a `data:` URI using `Image` + `ImageFit.COVER`
- ✅ Use `Card` + `Divider` + `Row` to compose a result card with metadata
- ✅ Install a `FakeBridge` in tests to exercise the full path without a browser

---

## Next steps

Try extending the example:

- 💡 Add a **Switch Camera** button that toggles `facing` between `"environment"` and `"user"`
- 💡 Use `native.http.upload` to send the captured photo to an API endpoint
- 💡 Explore [Weather (HTTP + geolocation)](./weather-native.en.md) — another native capability example with the same bridge pattern
- 💡 Read the [wire format contract](../wire-contract.md) to understand how `native_call`/`native_result` travel in Mode B
