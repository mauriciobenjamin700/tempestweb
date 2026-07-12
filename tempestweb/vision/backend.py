"""An ``ort-vision-sdk`` inference backend backed by the ``native.onnx`` bridge.

``ort-vision-sdk``'s task classes (``Detector`` / ``Classifier`` / ``Segmenter``)
drive inference through a single injectable :class:`InferenceBackend`; the default
runs ONNX Runtime in-process. That wheel does not exist under Pyodide, so this
backend bridges the model run to **onnxruntime-web** through tempestweb's
``native.onnx`` capability instead. Preprocessing, postprocessing and result
parsing stay in Python (NumPy) exactly as the SDK ships them — only the model
``run`` crosses the bridge.

Because the bridge is asynchronous (a ``postMessage`` round-trip to JS, which the
browser cannot run synchronously), the synchronous :meth:`NativeOnnxBackend.run`
raises; use a task's ``predict`` / ``ort_async_predict`` (both await the async
backend path). Tensors cross as base64 raw bytes + shape + dtype — the same wire
shape :class:`tempestweb.native.onnx.Tensor` already uses.
"""

from __future__ import annotations

import base64

import numpy as np
from numpy.typing import NDArray

from tempestweb.native.onnx import OnnxModel, Tensor
from tempestweb.native.onnx import load as onnx_load
from tempestweb.native.onnx import run as onnx_run

__all__ = ["NativeOnnxBackend"]


def _ndarray_to_tensor(array: NDArray[np.generic]) -> Tensor:
    """Encode a NumPy array as a bridge :class:`Tensor`.

    Args:
        array: The input array. Made C-contiguous before its raw bytes are read.

    Returns:
        The tensor carrying the array's little-endian bytes, shape and dtype.
    """
    contiguous = np.ascontiguousarray(array)
    return Tensor(
        data_base64=base64.b64encode(contiguous.tobytes()).decode("ascii"),
        dims=[int(d) for d in contiguous.shape],
        dtype=str(contiguous.dtype),
    )


def _tensor_to_ndarray(tensor: Tensor) -> NDArray[np.generic]:
    """Decode a bridge :class:`Tensor` back into a NumPy array.

    Args:
        tensor: The tensor returned by the bridge.

    Returns:
        The reconstructed array with the tensor's dtype and shape.
    """
    buffer = base64.b64decode(tensor.data_base64)
    flat = np.frombuffer(buffer, dtype=np.dtype(tensor.dtype))
    return flat.reshape(tuple(tensor.dims))


class NativeOnnxBackend:
    """An ``ort-vision-sdk`` backend that runs the model over ``native.onnx``.

    Satisfies ``ort_vision_sdk.InferenceBackend``. Build it with the async
    :meth:`create` factory (loading crosses the bridge), then inject it into a
    task: ``Detector("", backend=backend)``. The synchronous :meth:`run` is
    unsupported in the browser — use the async ``predict`` path.

    Attributes:
        model: The loaded :class:`~tempestweb.native.onnx.OnnxModel` handle.
    """

    def __init__(self, model: OnnxModel) -> None:
        """Wrap a loaded bridge session.

        Args:
            model: The :class:`~tempestweb.native.onnx.OnnxModel` from
                :func:`tempestweb.native.onnx.load`.
        """
        self.model: OnnxModel = model

    @classmethod
    async def create(
        cls, model_url: str, *, providers: list[str] | None = None
    ) -> NativeOnnxBackend:
        """Load an onnxruntime-web session and wrap it as a backend.

        Args:
            model_url: URL/path of the ``.onnx`` model (same-origin in the
                artifact, e.g. ``"./models/yolov8n.onnx"``).
            providers: Execution providers in preference order (defaults to
                ``["wasm"]`` on the JS side).

        Returns:
            The ready :class:`NativeOnnxBackend`.
        """
        model = await onnx_load(model_url, providers=providers)
        return cls(model)

    @property
    def input_names(self) -> list[str]:
        """Names of the model's inputs, in declaration order."""
        return list(self.model.input_names)

    @property
    def input_name(self) -> str:
        """Name of the first (and usually only) input."""
        return self.model.input_name

    @property
    def input_shapes(self) -> list[tuple[int | str, ...]]:
        """Declared input shapes. Empty — the bridge does not report shapes."""
        return []

    @property
    def input_shape(self) -> tuple[int | str, ...]:
        """Declared shape of the first input. Empty (see :pyattr:`input_shapes`)."""
        return ()

    @property
    def output_names(self) -> list[str]:
        """Names of the model's outputs, in declaration order."""
        return list(self.model.output_names)

    @property
    def output_shapes(self) -> list[tuple[int | str, ...]]:
        """Declared output shapes. Empty — tasks fall back to labels/runtime shape."""
        return []

    def run(
        self,
        feeds: dict[str, NDArray[np.generic]],
        *,
        output_names: list[str] | None = None,
    ) -> list[NDArray[np.generic]]:
        """Synchronous inference — unsupported over the async browser bridge.

        Args:
            feeds: Mapping of input name to array.
            output_names: Outputs to fetch (unused).

        Raises:
            RuntimeError: Always. The ``native.onnx`` bridge is asynchronous;
                use a task's ``predict`` / ``ort_async_predict`` instead.
        """
        raise RuntimeError(
            "NativeOnnxBackend has no synchronous run (the native.onnx bridge is "
            "async). Use `await task.predict(...)` or `task.ort_async_predict(...)`."
        )

    async def async_run(
        self,
        feeds: dict[str, NDArray[np.generic]],
        *,
        output_names: list[str] | None = None,
    ) -> list[NDArray[np.generic]]:
        """Run inference over the bridge, returning outputs in order.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Output names to fetch, in order. ``None`` returns all
                outputs in the model's declared order.

        Returns:
            One array per requested output, in order.
        """
        return await self._run(feeds, output_names)

    async def ort_async_run(
        self,
        feeds: dict[str, NDArray[np.generic]],
        *,
        output_names: list[str] | None = None,
    ) -> list[NDArray[np.generic]]:
        """High-concurrency async variant — delegates to :meth:`async_run`."""
        return await self._run(feeds, output_names)

    async def _run(
        self,
        feeds: dict[str, NDArray[np.generic]],
        output_names: list[str] | None,
    ) -> list[NDArray[np.generic]]:
        """Encode feeds, cross the bridge, decode outputs in the requested order.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Output names to fetch in order, or ``None`` for all.

        Returns:
            One decoded array per requested output.
        """
        tensor_feeds = {name: _ndarray_to_tensor(arr) for name, arr in feeds.items()}
        outputs = await onnx_run(self.model.session_id, tensor_feeds)
        names = output_names or self.output_names or list(outputs)
        return [_tensor_to_ndarray(outputs[name]) for name in names]
