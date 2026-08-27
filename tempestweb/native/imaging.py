"""Compress, thumbnail and transform an image before it is uploaded (R6).

Between :func:`tempestweb.native.camera.capture` and
:func:`tempestweb.native.http.upload` there was nothing. An app captured a 4 MB
photo and uploaded 4 MB, or rewrote canvas compression by hand — in a framework
whose proposal is not writing JS.

**The pixels stay in the browser.** Every function here takes and returns an
:class:`ImageRef`, an opaque handle to bytes the client is holding. Python
addresses the image by name; the image never crosses the bridge:

```text
Mode B, a 4 MB photo, compressing it:

  bytes:   client →5.3MB→ server →5.3MB→ client   (10.6 MB of network)
  handle:  client →"blob:tw:7"→ server →"blob:tw:7"→ client   (~40 bytes)
```

Example:
    ```python
    from tempestweb import native


    async def upload_photo() -> None:
        photo = await native.camera.capture(include_bytes=False)
        small = await native.imaging.compress(photo, max_kb=200, max_width=1600)
        print(small.size_kb, small.quality, small.attempts, small.within_budget)
        await native.http.upload("/api/fotos", small.as_upload("foto.jpg"))
    ```

The part nobody gets right on the first try is the compression: it is a **binary
search of encoder quality against a byte budget**, because encoded size is not
linear in quality. :class:`CompressedImage` reports where it landed — which
quality, how many encodes it spent, and whether it met the budget at all.

!!! warning "An impossible budget answers, it does not hang"
    Asking for 200 KB of a photo that will not go below 400 KB at the floor
    quality gives ``within_budget=False`` and the smallest it managed, after a
    **bounded** number of encodes. A too-large image the app can decide about
    beats a spinner that never stops.

!!! note "Handles are bounded, and an evicted one is a named error"
    The client holds at most a few dozen blobs and evicts the oldest, so a photo
    app running for an hour does not accumulate every frame. Addressing an
    evicted handle raises ``NativeError("not_found")`` — recover by capturing
    again, not by retrying.
"""

from __future__ import annotations

import base64
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "ImageRef",
    "ImageSource",
    "CompressOptions",
    "TransformOptions",
    "CropBox",
    "CompressedImage",
    "Thumbnail",
    "ProcessedImage",
    "ImageInfo",
    "ImageBytes",
    "AUTO_TYPE",
    "compress",
    "thumbnails",
    "transform",
    "info",
    "read",
    "release",
]

#: Ask the browser to pick the smallest type it can encode (WebP where
#: available, JPEG otherwise). One field instead of the two capabilities the
#: React SDK spends on it: the caller wants a small file, not a survey.
AUTO_TYPE = "auto"

#: An opaque handle to bytes the client is holding. Never parsed here — its shape
#: is the client's business, and Python only ever hands it back.
ImageRef = str

#: What a capability accepts as an image: a handle, or any model carrying one
#: (a :class:`~tempestweb.native.camera.Photo`, a
#: :class:`~tempestweb.native.file.PickedFile`, or a result from this module).
ImageSource = "ImageRef | BaseModel | dict[str, Any]"


class _Payload(BaseModel):
    """Base for a model the **browser** fills in.

    Extras are ignored on purpose: a newer client sending a field an older Python
    does not know about must not break that Python. The opposite rule applies to
    the option models below.
    """

    model_config = ConfigDict(frozen=True)


class _Options(BaseModel):
    """Base for a model the **developer** fills in.

    ``extra="forbid"`` because a misspelled option is a bug and has to hurt. The
    alternative — silently ignoring ``max_width`` because it was typed
    ``maxWidth`` — uploads a full-size photo and says nothing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class CropBox(_Options):
    """A rectangle to cut out of the source, in source pixels.

    Attributes:
        x: Left edge.
        y: Top edge.
        width: Rectangle width.
        height: Rectangle height.
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class CompressOptions(_Options):
    """How hard to compress, and what to aim for.

    Attributes:
        max_kb: The byte budget in kilobytes. ``None`` compresses without a
            target, which just re-encodes at ``max_quality``.
        max_width: Cap the width, keeping the aspect ratio. Never upscales.
        max_height: Cap the height, keeping the aspect ratio. Never upscales.
        type: The output MIME type, or :data:`AUTO_TYPE`.
        min_quality: The floor the search will not go below.
        max_quality: The ceiling the search starts from.
        steps: How many encodes the search may spend. Bounding this is what makes
            an impossible budget answer instead of hang.
    """

    max_kb: float | None = None
    max_width: int | None = None
    max_height: int | None = None
    type: str = AUTO_TYPE
    min_quality: float = 0.4
    max_quality: float = 0.92
    steps: int = 6


class TransformOptions(_Options):
    """Resize, rotate, crop and flip, in one pass over the image.

    One call rather than four, because four means decoding and encoding the same
    image four times to do what one canvas does once.

    Attributes:
        width: Cap the width, keeping the aspect ratio.
        height: Cap the height, keeping the aspect ratio.
        rotate: Degrees clockwise. 90 and 270 swap the output's axes.
        flip_horizontal: Mirror left-to-right.
        flip_vertical: Mirror top-to-bottom.
        crop: A rectangle to cut out before the rest is applied.
        type: The output MIME type, or :data:`AUTO_TYPE`.
        quality: The encoder quality for the single encode.
    """

    width: int | None = None
    height: int | None = None
    rotate: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    crop: CropBox | None = None
    type: str = AUTO_TYPE
    quality: float = 0.92


class _Handled(_Payload):
    """A payload carrying a handle to bytes the client is holding."""

    ref: ImageRef = ""
    mime_type: str = "application/octet-stream"

    def as_upload(self, name: str) -> dict[str, Any]:
        """Describe this image for :func:`tempestweb.native.http.upload`.

        The whole point of the handle: the upload reads the bytes on the client,
        so they are sent once, to the server that wanted them — not once to
        Python and again to the server.

        Args:
            name: The file name to send.

        Returns:
            The file descriptor ``http.upload`` expects.
        """
        return {"name": name, "type": self.mime_type, "blob_id": self.ref}


class CompressedImage(_Handled):
    """What the quality search settled on.

    Attributes:
        ref: The handle to the compressed bytes.
        mime_type: What it was encoded to — useful when ``type`` was ``"auto"``.
        width: The output width in pixels.
        height: The output height in pixels.
        size_kb: The output size in kilobytes.
        quality: The encoder quality the search chose.
        attempts: How many encodes it spent getting there.
        within_budget: Whether ``max_kb`` was met. **Check this** — ``False``
            means the budget was impossible and this is the smallest it managed.
    """

    width: int = 0
    height: int = 0
    size_kb: float = 0.0
    quality: float = 0.0
    attempts: int = 0
    within_budget: bool = False


class Thumbnail(_Handled):
    """One rendered preview.

    Attributes:
        ref: The handle to the thumbnail's bytes.
        mime_type: What it was encoded to.
        size: The requested maximum edge, echoed back so a caller can match a
            thumbnail to the size it asked for without relying on order.
        width: The actual width, after fitting the aspect ratio.
        height: The actual height.
        size_kb: The size in kilobytes.
    """

    size: int = 0
    width: int = 0
    height: int = 0
    size_kb: float = 0.0


class ProcessedImage(_Handled):
    """The result of a transform.

    Attributes:
        ref: The handle to the processed bytes.
        mime_type: What it was encoded to.
        width: The output width.
        height: The output height.
        size_kb: The output size in kilobytes.
    """

    width: int = 0
    height: int = 0
    size_kb: float = 0.0


class ImageInfo(_Payload):
    """What an image is, without moving it.

    Attributes:
        mime_type: The image's MIME type.
        width: The intrinsic width in pixels.
        height: The intrinsic height in pixels.
        size_kb: The byte size in kilobytes.
    """

    mime_type: str = "application/octet-stream"
    width: int = 0
    height: int = 0
    size_kb: float = 0.0


class ImageBytes(_Payload):
    """An image pulled back into Python.

    Attributes:
        data_base64: The bytes, base64-encoded.
        mime_type: The image's MIME type.
        size_kb: The byte size in kilobytes.
    """

    data_base64: str = Field(default="", repr=False)
    mime_type: str = "application/octet-stream"
    size_kb: float = 0.0

    def to_bytes(self) -> bytes:
        """Decode to raw bytes.

        Returns:
            The decoded image bytes.
        """
        return base64.b64decode(self.data_base64)


def _source(source: object) -> object:
    """Render whatever the caller passed as the wire's ``source`` field.

    Args:
        source: A handle, a model carrying one, or a payload carrying base64.

    Returns:
        The handle when one can be found, otherwise the value itself — the client
        also accepts ``{data_base64, mime_type}``, which is what
        ``camera.capture`` and ``file.pick`` answered before handles existed.
    """
    if isinstance(source, str):
        return source
    ref = getattr(source, "ref", None)
    if isinstance(ref, str) and ref:
        return ref
    if isinstance(source, BaseModel):
        return source.model_dump()
    return source


async def compress(
    source: object,
    *,
    options: CompressOptions | None = None,
    **overrides: Any,  # noqa: ANN401 — the CompressOptions fields, spelled inline
) -> CompressedImage:
    """Shrink an image to fit a byte budget, by searching encoder quality.

    Args:
        source: The image: a handle, a ``Photo``, a ``PickedFile``, or a previous
            result from this module.
        options: The options, built explicitly.
        **overrides: The same fields spelled inline —
            ``compress(photo, max_kb=200)``. A misspelled name **raises**, because
            silently ignoring ``maxWidth`` uploads a full-size photo and says
            nothing.

    Returns:
        The :class:`CompressedImage`. **Check ``within_budget``**: ``False`` means
        the budget could not be met and this is the smallest it managed.

    Raises:
        ValidationError: If an override is not a :class:`CompressOptions` field.
        NativeError: If the handle is unknown or evicted (``not_found``), the
            bytes are not an image (``decode_failed``), or the browser cannot
            encode the requested type (``encode_failed``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    resolved = options if options is not None else CompressOptions(**overrides)
    value = await send_native_call(
        "imaging.compress",
        {"source": _source(source), **resolved.model_dump(exclude_none=True)},
    )
    return CompressedImage.model_validate(value)


async def thumbnails(
    source: object,
    sizes: list[int],
    *,
    type: str = AUTO_TYPE,
    quality: float = 0.92,
) -> list[Thumbnail]:
    """Render one image at several sizes, for previews.

    Args:
        source: The image, in any form :func:`compress` accepts.
        sizes: The maximum edge of each thumbnail, in pixels.
        type: The output MIME type, or :data:`AUTO_TYPE`.
        quality: The encoder quality.

    Returns:
        One :class:`Thumbnail` per requested size, in the order asked. An empty
        ``sizes`` returns ``[]`` — asking for no thumbnails is valid, not an
        error.

    Raises:
        NativeError: If the handle is unknown or evicted (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "imaging.thumbnails",
        {
            "source": _source(source),
            "sizes": list(sizes),
            "type": type,
            "quality": quality,
        },
    )
    raw = value.get("thumbnails", [])
    if not isinstance(raw, list):
        return []
    return [Thumbnail.model_validate(item) for item in raw]


async def transform(
    source: object,
    *,
    options: TransformOptions | None = None,
    **overrides: Any,  # noqa: ANN401 — the TransformOptions fields, spelled inline
) -> ProcessedImage:
    """Resize, rotate, crop and flip in a single pass.

    Args:
        source: The image, in any form :func:`compress` accepts.
        options: The options, built explicitly.
        **overrides: The same fields spelled inline. A misspelled name raises.

    Returns:
        The :class:`ProcessedImage`.

    Raises:
        ValidationError: If an override is not a :class:`TransformOptions` field.
        NativeError: If the handle is unknown or evicted (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    resolved = options if options is not None else TransformOptions(**overrides)
    value = await send_native_call(
        "imaging.transform",
        {"source": _source(source), **resolved.model_dump(exclude_none=True)},
    )
    return ProcessedImage.model_validate(value)


async def info(source: object) -> ImageInfo:
    """Report an image's type, size and dimensions without moving it.

    Cheap by design: the byte count and MIME come from the blob itself. An app
    deciding whether an image is worth compressing at all asks this first.

    Args:
        source: The image, in any form :func:`compress` accepts.

    Returns:
        The :class:`ImageInfo`.

    Raises:
        NativeError: If the handle is unknown or evicted (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    return ImageInfo.model_validate(
        await send_native_call("imaging.info", {"source": _source(source)})
    )


async def read(source: object) -> ImageBytes:
    """Pull an image's bytes back into Python.

    The escape hatch, **not** the path. This moves the whole image across the
    bridge, which is what handles exist to avoid — an app that only needs to
    upload should hand the handle to :func:`tempestweb.native.http.upload` via
    :meth:`CompressedImage.as_upload`.

    Args:
        source: The image, in any form :func:`compress` accepts.

    Returns:
        The :class:`ImageBytes`.

    Raises:
        NativeError: If the handle is unknown or evicted (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    return ImageBytes.model_validate(
        await send_native_call("imaging.read", {"source": _source(source)})
    )


async def release(source: object | None = None, *, all: bool = False) -> int:
    """Release a handle, or every handle.

    Handles are evicted automatically once the registry is full, so this is an
    optimisation rather than a duty — worth calling when a screen holding several
    large images is left.

    Args:
        source: The handle to release.
        all: Release every handle instead.

    Returns:
        How many handles were released. Releasing one that is already gone
        answers ``0`` rather than raising — a double release is not an error.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    args: dict[str, Any] = {"all": all}
    if source is not None:
        args["source"] = _source(source)
    value = await send_native_call("imaging.release", args)
    released = value.get("released", 0)
    return int(released) if isinstance(released, int | float) else 0
