"""Native camera capture capability over the browser's MediaDevices API (N4).

Capture always happens **in the browser** — there is no server-side camera. In
Mode A ``client/native/camera.js`` calls ``navigator.mediaDevices.getUserMedia``
and grabs a frame in-process; in Mode B the ``camera.capture`` ``native_call`` is
proxied to the client, the photo is captured there, and the bytes ride back over
the transport (so the payload should be compressed before the round-trip).

The capture is returned as a typed :class:`Photo` carrying base64-encoded bytes;
:meth:`Photo.to_bytes` decodes them for upload via :mod:`tempestweb.native.http`.
"""

from __future__ import annotations

import base64

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import send_native_call

__all__ = ["Photo", "capture"]


class Photo(BaseModel):
    """A captured photo returned by the browser.

    Attributes:
        mime_type: The image MIME type (e.g. ``"image/jpeg"``, ``"image/png"``).
        width: Frame width in pixels.
        height: Frame height in pixels.
        data_base64: The image bytes, base64-encoded (JSON-safe over the wire).
            Empty when the capture asked not to carry them — see ``ref``.
        ref: An opaque handle to the same bytes, still held by the client. Hand
            it to :mod:`tempestweb.native.imaging` to compress or transform the
            photo **without moving the pixels across the bridge**, and to
            :func:`tempestweb.native.http.upload` to send them straight to the
            server.
    """

    model_config = ConfigDict(frozen=True)

    mime_type: str = "image/jpeg"
    width: int = 0
    height: int = 0
    data_base64: str = Field(default="", repr=False)
    ref: str = ""

    def to_bytes(self) -> bytes:
        """Decode the photo to raw bytes.

        Returns:
            The decoded image bytes.
        """
        return base64.b64decode(self.data_base64)


async def capture(
    *,
    facing: str = "environment",
    quality: float = 0.85,
    mime_type: str = "image/jpeg",
    include_bytes: bool = True,
) -> Photo:
    """Capture a single photo from the device camera.

    Args:
        facing: Preferred camera (``"environment"`` rear, ``"user"`` front).
        quality: Encoding quality in ``[0.0, 1.0]`` for lossy formats.
        mime_type: The desired output image MIME type.
        include_bytes: Whether to carry the image bytes back to Python. Pass
            ``False`` when the photo is only going to be compressed and uploaded:
            the bytes then never cross the bridge at all, and
            :attr:`Photo.ref` addresses them where they already are. A 4 MB photo
            crosses as ~5.3 MB of base64, which in Mode B is a network trip.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the user denies camera permission (``permission_denied``),
            no camera is present (``unavailable``), or the page is not a secure
            context (``insecure_context``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    clamped = max(0.0, min(1.0, quality))
    value = await send_native_call(
        "camera.capture",
        {
            "facing": facing,
            "quality": clamped,
            "mime_type": mime_type,
            "include_bytes": include_bytes,
        },
    )
    return Photo.model_validate(value)
