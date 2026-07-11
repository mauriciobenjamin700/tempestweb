"""Native media-recording capability over the MediaRecorder Web API.

:func:`start` sends a ``recorder.start`` ``native_call`` and gets back an opaque
recording id; ``client/native/recorder.js`` opens the requested source
(``getUserMedia`` for the microphone, ``getDisplayMedia`` for the screen), starts a
``MediaRecorder``, and stores it in a registry keyed by that id. :func:`stop` sends
``recorder.stop`` with the id so the client can finalize the matching recorder and
return the captured bytes. The Python side never touches the recorder — it only
shuttles the id.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = ["Recording", "start", "stop"]


@dataclass(frozen=True)
class Recording:
    """A finalized media recording.

    Attributes:
        data_base64: The recorded bytes, base64-encoded (JSON-safe over the wire).
        mime_type: The recording MIME type (e.g. ``"audio/webm"``).
        size: The recorded byte length.
    """

    data_base64: str
    mime_type: str
    size: int


async def start(source: str = "microphone", mime_type: str = "") -> str:
    """Start recording media from a source.

    Args:
        source: The capture source, ``"microphone"`` or ``"screen"``.
        mime_type: The desired recording MIME type; the browser default when empty.

    Returns:
        An opaque recording id to pass back to :func:`stop`. The client holds the
        underlying ``MediaRecorder`` in a registry keyed by this id.

    Raises:
        NativeError: If capture is refused (``permission_denied``) or the API is
            unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "recorder.start",
        {"source": source, "mime_type": mime_type},
    )
    return str(value.get("id", ""))


async def stop(recording_id: str) -> Recording:
    """Stop a recording and return the captured media.

    Args:
        recording_id: The opaque id returned by :func:`start`.

    Returns:
        The finalized :class:`Recording` carrying base64 bytes, MIME type and size.

    Raises:
        NativeError: If the recording id is unknown (``not_found``) or the API is
            unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("recorder.stop", {"id": recording_id})
    return Recording(
        data_base64=str(value.get("data_base64", "")),
        mime_type=str(value.get("mime_type", "")),
        size=int(value.get("size", 0)),
    )
