"""Fetch a compact tabular model's bytes (``.tmc``) for the in-Python reader.

The compact format runs a tabular model with **no inference runtime at all**:
``onnxruntime-web`` is 13.96 MB of WebAssembly (3.58 MB gzipped) against a linear
model of 660 bytes, so for an app whose only model is tabular the runtime *is*
the download. The reader lives in :mod:`tempestweb.tabular.compact`; this
capability exists only because Python in the browser cannot fetch.

``compact.load`` ``{model_url}`` → ``{bytes, size}``, the bytes base64-encoded,
fetched through the same asset cache ``onnx.load`` uses — so a model downloads
once per version rather than once per session.
"""

from __future__ import annotations

import base64

from tempestweb.native.dispatch import send_native_call

__all__ = ["load"]


async def load(model_url: str) -> bytes:
    """Download a compact model and hand back its raw bytes.

    Args:
        model_url: URL/path of the ``.tmc`` file, same-origin in the artifact
            (e.g. ``"/models/risk.tmc"``).

    Returns:
        The file's bytes, ready for :func:`tempestweb.tabular.compact.parse`.

    Raises:
        NativeError: If the model cannot be downloaded (``model_load``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("compact.load", {"model_url": model_url})
    return base64.b64decode(str(value.get("bytes", "")))
