"""JSON-serializable schemas for computer-vision predictions.

``ort-vision-sdk`` returns Ultralytics-style result objects (great in Python, not
JSON responses). These Pydantic schemas are the wire shape to send to a backend
or store; :mod:`tempestweb.vision.mapping` converts a result object into them.

They deliberately mirror ``tempest_fastapi_sdk.vision`` field-for-field, so a
tempestweb client and a tempest-fastapi-sdk endpoint speak the **same** shape
end to end — without either package depending on the other.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "BoundingBoxSchema",
    "ClassProbabilitySchema",
    "ClassificationSchema",
    "DetectionSchema",
    "SegmentationSchema",
]


class BoundingBoxSchema(BaseModel):
    """An axis-aligned box in pixel coordinates (top-left origin)."""

    x1: float = Field(description="Left edge (px).")
    y1: float = Field(description="Top edge (px).")
    x2: float = Field(description="Right edge (px).")
    y2: float = Field(description="Bottom edge (px).")


class DetectionSchema(BaseModel):
    """A single detected object."""

    class_id: int = Field(description="Integer class index.")
    class_name: str = Field(description="Human-readable label.")
    confidence: float = Field(description="Detection score in [0, 1].")
    box: BoundingBoxSchema = Field(description="Object bounding box.")


class ClassProbabilitySchema(BaseModel):
    """One class score from a classifier's ranked output."""

    class_id: int = Field(description="Integer class index.")
    class_name: str = Field(description="Human-readable label.")
    probability: float = Field(description="Score in [0, 1].")


class ClassificationSchema(BaseModel):
    """A classification result: the top label plus the ranked scores."""

    class_id: int = Field(description="Top-1 class index.")
    class_name: str = Field(description="Top-1 label.")
    confidence: float = Field(description="Top-1 score in [0, 1].")
    probabilities: list[ClassProbabilitySchema] = Field(
        default_factory=list,
        description="Ranked class scores (top-k), highest first.",
    )


class SegmentationSchema(BaseModel):
    """A single segmented instance (box + label; mask pixels omitted)."""

    class_id: int = Field(description="Integer class index.")
    class_name: str = Field(description="Human-readable label.")
    confidence: float = Field(description="Instance score in [0, 1].")
    box: BoundingBoxSchema = Field(description="Instance bounding box.")
