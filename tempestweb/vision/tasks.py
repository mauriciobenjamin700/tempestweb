"""Vision task classes — ``Classifier`` / ``Detector`` / ``Segmenter``.

Thin async wrappers around ``ort-vision-sdk``'s task classes, wired to the
:class:`~tempestweb.vision.backend.NativeOnnxBackend` so inference runs over the
``native.onnx`` bridge (onnxruntime-web) instead of the ONNX Runtime wheel. The
result objects returned are exactly ``ort-vision-sdk``'s
(``DetectionResults`` / ``ClassificationResults`` / ``SegmentationResults``) —
same ``.boxes`` / ``.probs`` / ``.masks`` surface — so existing ``ort-vision-sdk``
post-processing ports unchanged. Map them to JSON with
:mod:`tempestweb.vision.mapping`.

Because the bridge is async, construction and prediction are async:

    det = await Detector.create("./models/yolov8n.onnx", labels="coco")
    result = (await det.predict("./images/street.jpg"))[0]
    for d in result:
        print(d.name, d.conf, d.box.xyxy)
    schemas = to_detection_schemas(result)  # POST to a tempest-fastapi-sdk backend
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ort_vision_sdk import Classifier as _Classifier
from ort_vision_sdk import Detector as _Detector
from ort_vision_sdk import Segmenter as _Segmenter

from tempestweb.vision.backend import NativeOnnxBackend

if TYPE_CHECKING:
    from ort_vision_sdk import (
        ClassificationResults,
        DetectionResults,
        ImageInput,
        SegmentationResults,
    )

__all__ = ["Classifier", "Detector", "Segmenter"]

_Task = TypeVar("_Task", _Classifier, _Detector, _Segmenter)


class _VisionTask(Generic[_Task]):
    """Base async wrapper binding an ``ort-vision-sdk`` task to the bridge.

    Attributes:
        task: The wrapped ``ort-vision-sdk`` task instance.
    """

    _factory: type[_Task]

    def __init__(self, task: _Task) -> None:
        """Wrap a constructed ``ort-vision-sdk`` task.

        Args:
            task: The underlying task (already holding a
                :class:`NativeOnnxBackend`).
        """
        self.task: _Task = task

    @classmethod
    async def _build(
        cls,
        model_url: str,
        *,
        providers: list[str] | None = None,
        **task_kwargs: Any,  # noqa: ANN401 - forwarded verbatim to ort-vision-sdk
    ) -> _Task:
        """Load the model over the bridge and construct the underlying task.

        Args:
            model_url: URL/path of the ``.onnx`` model.
            providers: Execution providers for the onnxruntime-web session.
            **task_kwargs: Forwarded verbatim to the ``ort-vision-sdk`` task
                constructor (e.g. ``labels``, ``input_size``, ``conf_threshold``).

        Returns:
            The constructed ``ort-vision-sdk`` task, backed by the bridge.
        """
        backend = await NativeOnnxBackend.create(model_url, providers=providers)
        return cls._factory("", backend=backend, **task_kwargs)

    @property
    def labels(self) -> tuple[str, ...]:
        """Class labels indexed by class id."""
        return self.task.labels


class Detector(_VisionTask[_Detector]):
    """Object detection over the ``native.onnx`` bridge (async)."""

    _factory = _Detector

    @classmethod
    async def create(
        cls,
        model_url: str,
        *,
        providers: list[str] | None = None,
        **task_kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk Detector
    ) -> Detector:
        """Load a detection model and return a ready :class:`Detector`.

        Args:
            model_url: URL/path of the ``.onnx`` model.
            providers: onnxruntime-web execution providers.
            **task_kwargs: Forwarded to ``ort_vision_sdk.Detector`` (``labels``,
                ``input_size``, ``conf_threshold``, ``iou_threshold``, …).

        Returns:
            The ready detector.
        """
        return cls(await cls._build(model_url, providers=providers, **task_kwargs))

    async def predict(
        self,
        image: ImageInput,
        **kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk predict
    ) -> list[DetectionResults]:
        """Detect objects in an image (async).

        Args:
            image: Image source (path, bytes, ``np.ndarray`` or ``PIL.Image``).
            **kwargs: Forwarded to ``ort-vision-sdk`` (``conf_threshold``,
                ``iou_threshold``, ``classes``).

        Returns:
            A 1-element list with the :class:`DetectionResults` envelope.
        """
        return await self.task.ort_async_predict(image, **kwargs)


class Classifier(_VisionTask[_Classifier]):
    """Image classification over the ``native.onnx`` bridge (async)."""

    _factory = _Classifier

    @classmethod
    async def create(
        cls,
        model_url: str,
        *,
        providers: list[str] | None = None,
        **task_kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk Classifier
    ) -> Classifier:
        """Load a classification model and return a ready :class:`Classifier`.

        Args:
            model_url: URL/path of the ``.onnx`` model.
            providers: onnxruntime-web execution providers.
            **task_kwargs: Forwarded to ``ort_vision_sdk.Classifier`` (``labels``,
                ``input_size``, …).

        Returns:
            The ready classifier.
        """
        return cls(await cls._build(model_url, providers=providers, **task_kwargs))

    async def predict(
        self,
        image: ImageInput,
        **kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk predict
    ) -> list[ClassificationResults]:
        """Classify an image (async).

        Args:
            image: Image source (path, bytes, ``np.ndarray`` or ``PIL.Image``).
            **kwargs: Forwarded to ``ort-vision-sdk``.

        Returns:
            A 1-element list with the :class:`ClassificationResults`.
        """
        return await self.task.ort_async_predict(image, **kwargs)


class Segmenter(_VisionTask[_Segmenter]):
    """Instance segmentation over the ``native.onnx`` bridge (async)."""

    _factory = _Segmenter

    @classmethod
    async def create(
        cls,
        model_url: str,
        *,
        providers: list[str] | None = None,
        **task_kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk Segmenter
    ) -> Segmenter:
        """Load a segmentation model and return a ready :class:`Segmenter`.

        Args:
            model_url: URL/path of the ``.onnx`` model.
            providers: onnxruntime-web execution providers.
            **task_kwargs: Forwarded to ``ort_vision_sdk.Segmenter`` (``labels``,
                ``input_size``, ``conf_threshold``, ``iou_threshold``, …).

        Returns:
            The ready segmenter.
        """
        return cls(await cls._build(model_url, providers=providers, **task_kwargs))

    async def predict(
        self,
        image: ImageInput,
        **kwargs: Any,  # noqa: ANN401 - forwarded to ort-vision-sdk predict
    ) -> list[SegmentationResults]:
        """Segment instances in an image (async).

        Args:
            image: Image source (path, bytes, ``np.ndarray`` or ``PIL.Image``).
            **kwargs: Forwarded to ``ort-vision-sdk`` (``conf_threshold``,
                ``iou_threshold``, …).

        Returns:
            A 1-element list with the :class:`SegmentationResults` envelope.
        """
        return await self.task.ort_async_predict(image, **kwargs)
