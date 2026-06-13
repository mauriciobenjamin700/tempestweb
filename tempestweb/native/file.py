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

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = ["SaveResult", "save"]


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
