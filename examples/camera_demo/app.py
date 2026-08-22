"""Camera demo — a live preview that reports frames, and a QR scanner.

Two widgets that need the camera itself, not a one-shot photo:

* :class:`~tempest_core.widgets.media.CameraPreview` shows the stream and calls
  ``on_frame`` every ``frame_interval_ms`` with the sampled frame (size, rotation
  and the bytes as base64) — the shape for "look at what the camera sees",
  whether that means a QR pipeline of your own, a document edge detector, or the
  vision SDK.
* :class:`~tempest_core.widgets.media.QrScanner` shows the same stream and calls
  ``on_scan`` with a decoded code, using the platform's own ``BarcodeDetector``.

Both need a **secure context** for the camera: ``localhost`` counts, so this runs
as-is; a deployment needs HTTPS. The reader is asked for permission by the
browser, once.

    tempestweb run --mode server --path examples/camera_demo
    tempestweb run --mode wasm --path examples/camera_demo

!!! note
    ``BarcodeDetector`` is Chrome/Android only today. Where it is missing the
    scanner still shows the camera and says so in the console — this client ships
    no runtime dependencies, so there is no bundled decoder to fall back on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import CameraFrameEvent, QrScanEvent
from tempest_core.widgets.media import CameraPreview, QrScanner

#: How often the preview samples a frame. 500ms is deliberately slow: in Mode B
#: every frame is a round trip, and this demo only needs to prove they arrive.
FRAME_INTERVAL_MS = 500

#: How many scanned codes to keep on screen.
HISTORY = 5


@dataclass
class CameraState:
    """State for the camera demo.

    Attributes:
        frames: How many frames the preview has reported.
        last_frame: The size of the most recent frame, as ``width x height``.
        last_bytes: How many base64 characters the last frame carried.
        codes: The most recently scanned codes, newest first.
    """

    frames: int = 0
    last_frame: str = "—"
    last_bytes: int = 0
    codes: list[str] = field(default_factory=list)


def make_state() -> CameraState:
    """Build the initial state.

    Returns:
        A fresh :class:`CameraState`.
    """
    return CameraState()


def view(app: App[CameraState]) -> Widget:
    """Render the preview, the scanner, and what each one has reported.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def framed(event: CameraFrameEvent) -> None:
        """Record a sampled frame.

        Args:
            event: The frame, carrying its size and bytes.
        """

        def mutate(state: CameraState) -> None:
            state.frames += 1
            state.last_frame = f"{event.width} × {event.height}"
            state.last_bytes = len(event.data)

        app.set_state(mutate)

    def scanned(event: QrScanEvent) -> None:
        """Record a decoded code, newest first.

        Args:
            event: The scan, carrying the decoded payload and its format.
        """

        def mutate(state: CameraState) -> None:
            state.codes = [event.data, *state.codes][:HISTORY]

        app.set_state(mutate)

    history: list[Widget] = [
        Text(content=code, key=f"code-{index}")
        for index, code in enumerate(app.state.codes)
    ]
    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Allow the camera when the browser asks.", key="title"),
            Row(
                key="cameras",
                style=Style(gap=12.0),
                children=[
                    CameraPreview(
                        key="preview",
                        facing="back",
                        frame_interval_ms=FRAME_INTERVAL_MS,
                        on_frame=framed,
                        style=Style(width=240.0, height=180.0, radius=12.0),
                    ),
                    QrScanner(
                        key="scanner",
                        on_scan=scanned,
                        style=Style(width=240.0, height=180.0, radius=12.0),
                    ),
                ],
            ),
            Text(
                content=(
                    f"Frames: {app.state.frames} · last {app.state.last_frame} · "
                    f"{app.state.last_bytes} base64 chars"
                ),
                key="frames",
            ),
            Text(content=f"Codes scanned: {len(app.state.codes)}", key="codes-count"),
            Column(key="codes", style=Style(gap=4.0), children=history),
        ],
    )
