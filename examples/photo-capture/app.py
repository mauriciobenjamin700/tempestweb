"""Camera capture view — exercises ``native.camera.capture()`` (N4).

Like :mod:`examples.fetch.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates an async native-capability handler: pressing *Capture* runs an
``async`` handler that:

1. Flips the view into a ``CAPTURING`` loading state (showing a
   :class:`~tempestweb._core.widgets.Spinner`).
2. Awaits the injected ``capture`` callable (defaults to
   ``native.camera.capture``), which resolves to a :class:`~tempestweb.native.Photo`
   carrying the MIME type, pixel dimensions, and base64-encoded bytes.
3. Renders the result in a :class:`~tempestweb._core.components.Card` with a
   data-URI :class:`~tempestweb._core.widgets.Image` preview and metadata row.

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

from tempestweb._core.style import AlignItems, Edge, FontWeight, JustifyContent

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card, Divider
from tempestweb._core.widgets import Button, Column, Image, ImageFit, Row, Spinner, Text
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
    # Validate the base64 payload is well-formed (guards against accidental
    # padding errors introduced by the bridge or tests).
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
        """Drive the async capture flow through all lifecycle phases.

        Sets the state to ``CAPTURING``, awaits the injected capture callable,
        then transitions to either ``CAPTURED`` (success) or ``ERROR``
        (``NativeError`` or any unexpected exception).
        """
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
        A :class:`~tempestweb._core.components.Card` containing a label/value
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
