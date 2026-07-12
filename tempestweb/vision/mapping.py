"""Convert ``ort-vision-sdk`` result objects into JSON-ready schemas.

Each helper takes one element of a task's ``predict`` return list — an Ultralytics
-style result object — and returns the :mod:`tempestweb.vision.schemas` shape. They
only read public attributes of the result objects, so they carry no hard typing
dependency on ``ort-vision-sdk`` at import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tempestweb.vision.schemas import (
    BoundingBoxSchema,
    ClassificationSchema,
    ClassProbabilitySchema,
    DetectionSchema,
    SegmentationSchema,
)

if TYPE_CHECKING:
    from ort_vision_sdk import (
        ClassificationResults,
        DetectionResults,
        SegmentationResults,
    )

__all__ = [
    "to_classification_schema",
    "to_detection_schemas",
    "to_segmentation_schemas",
]


def _box(bbox: Any) -> BoundingBoxSchema:  # noqa: ANN401 - ort-vision-sdk BoundingBox
    """Build a :class:`BoundingBoxSchema` from an ``ort-vision-sdk`` box.

    Args:
        bbox: A box exposing ``as_xyxy() -> (x1, y1, x2, y2)``.

    Returns:
        The box in pixel xyxy form.
    """
    x1, y1, x2, y2 = bbox.as_xyxy()
    return BoundingBoxSchema(x1=x1, y1=y1, x2=x2, y2=y2)


def to_detection_schemas(results: DetectionResults) -> list[DetectionSchema]:
    """Map a detector result to a list of :class:`DetectionSchema`.

    Args:
        results: One element of ``Detector.predict``'s return list.

    Returns:
        One entry per detected object (``[]`` when nothing was detected).
    """
    return [
        DetectionSchema(
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            box=_box(d.bbox),
        )
        for d in results.detections
    ]


def to_classification_schema(results: ClassificationResults) -> ClassificationSchema:
    """Map a classifier result to a single :class:`ClassificationSchema`.

    Args:
        results: One element of ``Classifier.predict``'s return list.

    Returns:
        The top-1 label plus the ranked scores.
    """
    return ClassificationSchema(
        class_id=results.cls,
        class_name=results.name,
        confidence=results.conf,
        probabilities=[
            ClassProbabilitySchema(
                class_id=p.class_id,
                class_name=p.class_name,
                probability=p.probability,
            )
            for p in results.probabilities
        ],
    )


def to_segmentation_schemas(results: SegmentationResults) -> list[SegmentationSchema]:
    """Map a segmenter result to a list of :class:`SegmentationSchema`.

    Mask pixels are omitted (see :class:`SegmentationSchema`); only the box +
    label of each instance are returned.

    Args:
        results: One element of ``Segmenter.predict``'s return list.

    Returns:
        One entry per segmented instance.
    """
    return [
        SegmentationSchema(
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            box=_box(d.bbox),
        )
        for d in results.detections
    ]
