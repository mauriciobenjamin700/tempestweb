"""Native file-output capability — share or download a generated file.

The web sibling of a "save file" action. The browser has no synchronous file
write, so a generated blob is delivered one of two ways, decided on the client:
``navigator.share({files:[...]})`` when the Web Share API accepts files (mobile),
otherwise an ``<a download>`` click (desktop). ``client/native/file.js`` picks the
path and reports which one ran.

The capability is numpy-free and JSON-safe: file bytes cross the bridge as base64.
Use it to export a generated ZIP / spreadsheet / image built in Python.
"""

from __future__ import annotations

import base64

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import send_native_call

__all__ = ["PickedFile", "SaveResult", "pick", "save"]


class PickedFile(BaseModel):
    """A file chosen by the user via the native file picker.

    Attributes:
        data_base64: The file bytes, base64-encoded (no data-URI prefix).
        mime: The file's MIME type as reported by the browser.
        name: The original file name.
    """

    model_config = ConfigDict(frozen=True)

    data_base64: str = Field(default="", repr=False)
    mime: str = "application/octet-stream"
    name: str = ""

    def to_bytes(self) -> bytes:
        """Decode the picked file to raw bytes.

        Returns:
            The decoded file bytes.
        """
        return base64.b64decode(self.data_base64)


async def pick(*, accept: str = "image/*", capture: str | None = None) -> PickedFile:
    """Open a native file picker and return the chosen file's bytes.

    The FilePicker widget's event carries only a uri/name, not bytes; this
    capability opens an ``<input type="file">`` and reads the selection back as
    base64 — the gallery/upload path for an on-device pipeline.

    Args:
        accept: The accept filter (e.g. ``"image/*"``).
        capture: Optional capture hint (``"environment"`` / ``"user"``) to prefer
            the camera on mobile.

    Returns:
        The chosen :class:`PickedFile`.

    Raises:
        NativeError: If the user cancels (``cancelled``) or the read fails
            (``read_failed``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("file.pick", {"accept": accept, "capture": capture})
    return PickedFile.model_validate(value)


class SaveResult(BaseModel):
    """The outcome of a :func:`save` call.

    Attributes:
        method: How the file was delivered — ``"share"`` (Web Share API) or
            ``"download"`` (anchor download).
        shared: ``True`` when the file went through the Web Share API.
    """

    model_config = ConfigDict(frozen=True)

    method: str = "download"
    shared: bool = False


async def save(
    filename: str,
    data: bytes,
    *,
    mime_type: str = "application/octet-stream",
) -> SaveResult:
    """Share or download a generated file in the browser.

    Args:
        filename: The suggested file name (e.g. ``"famacha-historico.zip"``).
        data: The raw file bytes to deliver.
        mime_type: The file's MIME type (e.g. ``"application/zip"``).

    Returns:
        A :class:`SaveResult` describing how the file was delivered.

    Raises:
        NativeError: If the user cancels a share that cannot fall back
            (``share_cancelled``) or delivery otherwise fails.
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "file.save",
        {
            "filename": filename,
            "data_base64": base64.b64encode(data).decode("ascii"),
            "mime": mime_type,
        },
    )
    return SaveResult.model_validate(value)
