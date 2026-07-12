"""Computer-vision task classes for tempestweb apps (the ``[vision]`` extra).

Classification, detection and instance segmentation with the same input/output
contract as ``ort-vision-sdk`` and ``tempest-fastapi-sdk``'s vision layer — but
running the model over tempestweb's ``native.onnx`` bridge (onnxruntime-web) so
it works in the browser, where the ``onnxruntime`` Python wheel does not exist.

The task classes reuse ``ort-vision-sdk``'s preprocessing, postprocessing and
result objects unchanged; only the model run crosses the async bridge, so
construction and prediction are ``await``-ed:

    from tempestweb.vision import Detector, to_detection_schemas

    det = await Detector.create("./models/yolov8n.onnx", labels="coco")
    result = (await det.predict("./images/street.jpg"))[0]
    for d in result:
        print(d.name, d.conf, d.box.xyxy)          # Ultralytics-style views
    payload = to_detection_schemas(result)          # JSON for a fastapi-sdk backend

Requires the ``vision`` extra: ``pip install "tempestweb[vision]"`` (pulls
``ort-vision-sdk`` + ``numpy``).
"""

from __future__ import annotations

from tempestweb.vision.backend import NativeOnnxBackend
from tempestweb.vision.mapping import (
    to_classification_schema,
    to_detection_schemas,
    to_segmentation_schemas,
)
from tempestweb.vision.schemas import (
    BoundingBoxSchema,
    ClassificationSchema,
    ClassProbabilitySchema,
    DetectionSchema,
    SegmentationSchema,
)
from tempestweb.vision.tasks import Classifier, Detector, Segmenter

__all__ = [
    "BoundingBoxSchema",
    "ClassProbabilitySchema",
    "ClassificationSchema",
    "Classifier",
    "DetectionSchema",
    "Detector",
    "NativeOnnxBackend",
    "SegmentationSchema",
    "Segmenter",
    "to_classification_schema",
    "to_detection_schemas",
    "to_segmentation_schemas",
]
