"""Tests for the vision extra (tempestweb.vision) — bridge backend + mapping.

The live model run needs a browser (Pyodide + onnxruntime-web); here we test the
parts that stand alone: the NumPy↔Tensor wire conversion, the async backend
driving a mocked ``native.onnx`` bridge, and the result→schema mapping.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from tempestweb.native.onnx import OnnxModel, Tensor
from tempestweb.vision import (
    ClassificationSchema,
    DetectionSchema,
    NativeOnnxBackend,
    to_classification_schema,
    to_detection_schemas,
)
from tempestweb.vision import backend as backend_mod


def test_ndarray_tensor_roundtrip() -> None:
    """A NumPy array survives encode→decode across the bridge wire shape."""
    array = np.arange(12, dtype=np.float32).reshape(1, 3, 2, 2)
    tensor = backend_mod._ndarray_to_tensor(array)
    assert tensor.dims == [1, 3, 2, 2]
    assert tensor.dtype == "float32"
    restored = backend_mod._tensor_to_ndarray(tensor)
    assert restored.dtype == np.float32
    assert np.array_equal(restored, array)


def test_int64_tensor_roundtrip() -> None:
    array = np.array([[1, 2, 3]], dtype=np.int64)
    restored = backend_mod._tensor_to_ndarray(backend_mod._ndarray_to_tensor(array))
    assert restored.dtype == np.int64
    assert np.array_equal(restored, array)


def _model() -> OnnxModel:
    return OnnxModel(session_id="s1", input_names=["images"], output_names=["a", "b"])


def test_backend_run_is_sync_unsupported() -> None:
    """The synchronous run must refuse — the bridge is async."""
    backend = NativeOnnxBackend(_model())
    with pytest.raises(RuntimeError, match="async"):
        backend.run({"images": np.zeros((1, 3, 4, 4), dtype=np.float32)})


async def test_backend_async_run_roundtrips_and_orders_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ort_async_run encodes feeds, calls the bridge, decodes outputs in order."""
    captured: dict[str, Any] = {}

    async def fake_onnx_run(
        session_id: str, feeds: dict[str, Tensor]
    ) -> dict[str, Tensor]:
        captured["session_id"] = session_id
        captured["feeds"] = feeds
        # Echo two named outputs (declared order is a, b).
        return {
            "b": backend_mod._ndarray_to_tensor(np.array([2.0], dtype=np.float32)),
            "a": backend_mod._ndarray_to_tensor(np.array([1.0], dtype=np.float32)),
        }

    monkeypatch.setattr(backend_mod, "onnx_run", fake_onnx_run)
    backend = NativeOnnxBackend(_model())
    feed = np.ones((1, 2), dtype=np.float32)
    outputs = await backend.ort_async_run({"images": feed})

    assert captured["session_id"] == "s1"
    assert isinstance(captured["feeds"]["images"], Tensor)
    # Returned in the model's declared output order (a, b), not dict order.
    assert [float(o[0]) for o in outputs] == [1.0, 2.0]


async def test_backend_create_loads_via_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_load(
        model_url: str, *, providers: list[str] | None = None
    ) -> OnnxModel:
        assert model_url == "./m.onnx"
        return _model()

    monkeypatch.setattr(backend_mod, "onnx_load", fake_load)
    backend = await NativeOnnxBackend.create("./m.onnx")
    assert backend.input_name == "images"
    assert backend.output_names == ["a", "b"]


# --- mapping (duck-typed fakes matching ort-vision-sdk's read surface) ---


class _FakeBox:
    def __init__(self, xyxy: tuple[float, float, float, float]) -> None:
        self._xyxy = xyxy

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return self._xyxy


class _FakeDetection:
    def __init__(self) -> None:
        self.class_id = 2
        self.class_name = "car"
        self.confidence = 0.9
        self.bbox = _FakeBox((1.0, 2.0, 3.0, 4.0))


class _FakeDetResults:
    detections = [_FakeDetection()]


class _FakeProb:
    def __init__(self, cid: int, name: str, p: float) -> None:
        self.class_id = cid
        self.class_name = name
        self.probability = p


class _FakeClsResults:
    cls = 5
    name = "cat"
    conf = 0.8
    probabilities = [_FakeProb(5, "cat", 0.8), _FakeProb(3, "dog", 0.1)]


def test_to_detection_schemas() -> None:
    out = to_detection_schemas(_FakeDetResults())  # type: ignore[arg-type]
    assert len(out) == 1
    d = out[0]
    assert isinstance(d, DetectionSchema)
    assert (d.class_id, d.class_name, d.confidence) == (2, "car", 0.9)
    assert (d.box.x1, d.box.y1, d.box.x2, d.box.y2) == (1.0, 2.0, 3.0, 4.0)


def test_to_classification_schema() -> None:
    out = to_classification_schema(_FakeClsResults())  # type: ignore[arg-type]
    assert isinstance(out, ClassificationSchema)
    assert (out.class_id, out.class_name, out.confidence) == (5, "cat", 0.8)
    assert [p.class_name for p in out.probabilities] == ["cat", "dog"]
