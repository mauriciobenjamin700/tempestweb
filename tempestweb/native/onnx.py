"""Native ONNX inference capability over ``onnxruntime-web`` (Mode A WASM bridge).

``onnxruntime`` (the CPython C-extension) has no Pyodide wheel, so Python running
in the browser cannot run an ONNX graph in-process. This capability bridges the
gap: the graph runs in JavaScript via **onnxruntime-web** (the WASM build), driven
through the same ``native_call`` seam as every other capability. The app does its
pre/post-processing in Python (numpy + pillow, both available in Pyodide) and hands
only the raw tensor execution across the bridge.

The capability is intentionally numpy-free here — tempestweb has no numpy
dependency. Tensors cross the wire as base64-encoded raw bytes plus a shape and a
dtype string; the caller (which *does* have numpy) serializes its ``ndarray`` into
:class:`Tensor` and decodes the results back. ``client/native/onnx.js`` forces the
``wasm`` execution provider (WebGPU lacks some kernels) and caches sessions by id.

Two calls:

* ``onnx.load`` ``{model_url, providers}`` → :class:`OnnxModel` (a session id plus
  the model's input/output names), caching the session on the JS side.
* ``onnx.run`` ``{session_id, feeds}`` → ``{name: Tensor}`` output map.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import send_native_call

__all__ = ["OnnxModel", "Tensor", "load", "run"]


class Tensor(BaseModel):
    """A dense tensor crossing the bridge as base64-encoded raw bytes.

    Attributes:
        data_base64: The raw little-endian tensor bytes, base64-encoded.
        dims: The tensor shape (e.g. ``[1, 3, 640, 640]``).
        dtype: The element type as an onnxruntime-web type string
            (``"float32"``, ``"int64"``, ``"uint8"``, ...).
    """

    model_config = ConfigDict(frozen=True)

    data_base64: str = Field(default="", repr=False)
    dims: list[int] = Field(default_factory=list)
    dtype: str = "float32"


class OnnxModel(BaseModel):
    """A loaded onnxruntime-web session living on the JS side.

    Attributes:
        session_id: Opaque id used to address the cached session on ``onnx.run``.
        input_names: The model's input names, in declaration order.
        output_names: The model's output names, in declaration order.
    """

    model_config = ConfigDict(frozen=True)

    session_id: str
    input_names: list[str] = Field(default_factory=list)
    output_names: list[str] = Field(default_factory=list)

    @property
    def input_name(self) -> str:
        """Name of the first (and usually only) input.

        Returns:
            The first input name.

        Raises:
            IndexError: If the model declares no inputs.
        """
        return self.input_names[0]


async def load(model_url: str, *, providers: list[str] | None = None) -> OnnxModel:
    """Create an onnxruntime-web inference session from a model URL.

    Args:
        model_url: URL/path of the ``.onnx`` model (same-origin in the artifact,
            e.g. ``"./models/detect.onnx"``).
        providers: Execution providers in preference order. Defaults to
            ``["wasm"]`` — WebGPU is avoided because some kernels (e.g. Resize)
            are missing in the web build.

    Returns:
        The :class:`OnnxModel` handle (session id + input/output names).

    Raises:
        NativeError: If the model fails to download or compile (``model_load``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "onnx.load",
        {"model_url": model_url, "providers": providers or ["wasm"]},
    )
    return OnnxModel.model_validate(value)


async def run(session_id: str, feeds: dict[str, Tensor]) -> dict[str, Tensor]:
    """Run inference on a loaded session and return its outputs.

    Args:
        session_id: The :pyattr:`OnnxModel.session_id` of a loaded session.
        feeds: Mapping of input name to its :class:`Tensor`. Keys must match the
            model's input names.

    Returns:
        Mapping of output name to its :class:`Tensor`.

    Raises:
        NativeError: If the session id is unknown (``not_found``) or execution
            fails (``inference``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    payload: dict[str, Any] = {
        "session_id": session_id,
        "feeds": {name: tensor.model_dump() for name, tensor in feeds.items()},
    }
    value = await send_native_call("onnx.run", payload)
    outputs = value.get("outputs", {})
    if not isinstance(outputs, dict):
        return {}
    return {name: Tensor.model_validate(raw) for name, raw in outputs.items()}
