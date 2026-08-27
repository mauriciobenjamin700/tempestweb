"""The manifest: which features the model expects, and in what order.

This is the part worth bringing over. Without it, an ONNX model is a function
from an unlabelled vector of floats to a number — the **order** carries all the
meaning, and nothing checks it. An app that sends age and income the other way
round gets a plausible score that is wrong, and there is no error anywhere.

The manifest is written when the model is exported and shipped next to the
``.onnx`` file:

```json
{
  "version": "2026-08-27",
  "features": ["age", "income", "tenure_months"],
  "outputs": ["label", "probabilities"],
  "classes": ["low", "high"]
}
```

Example:
    >>> manifest = manifest_from_dict(
    ...     {"features": ["age", "income"], "version": "1"}
    ... )
    >>> manifest.vector({"income": 3200.0, "age": 30})
    [30.0, 3200.0]

Note the row was written income-first and came back age-first: the manifest
imposes the order, so a caller never has to remember it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tempestweb.tabular.errors import (
    ManifestError,
    MissingFeatureError,
    UnknownFeatureError,
)

__all__ = [
    "FeatureManifest",
    "manifest_from_dict",
    "manifest_from_json",
    "FEATURES_KEY",
    "VERSION_KEY",
    "OUTPUTS_KEY",
    "CLASSES_KEY",
]

#: The manifest key holding the ordered feature names.
FEATURES_KEY = "features"

#: The manifest key holding the model's version, for cache busting and logs.
VERSION_KEY = "version"

#: The manifest key naming the model's outputs, in declaration order.
OUTPUTS_KEY = "outputs"

#: The manifest key naming the class labels a classifier answers.
CLASSES_KEY = "classes"


@dataclass(frozen=True)
class FeatureManifest:
    """What a model expects, declared rather than remembered.

    Attributes:
        features: The feature names, **in the order the model was trained on**.
            The order is the contract; the names are what makes it checkable.
        version: The model version, for logs and cache busting.
        outputs: The model's output names, in declaration order.
        classes: The class labels a classifier answers, in index order. Empty for
            a regressor.
    """

    features: tuple[str, ...]
    version: str = ""
    outputs: tuple[str, ...] = ()
    classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject a manifest that cannot describe anything.

        Raises:
            ManifestError: If it declares no features, or declares one twice —
                a duplicate makes the order ambiguous, which is exactly what the
                manifest exists to fix.
        """
        if not self.features:
            raise ManifestError("a manifest must declare at least one feature")
        duplicates = sorted(
            {name for name in self.features if self.features.count(name) > 1}
        )
        if duplicates:
            raise ManifestError(
                "a manifest cannot declare a feature twice: " + ", ".join(duplicates)
            )

    def vector(
        self,
        row: Mapping[str, Any],
        *,
        strict: bool = True,
    ) -> list[float]:
        """Order one row into the vector the model expects.

        Args:
            row: The feature values, in any order.
            strict: Whether a feature the model does not declare is an error.
                On by default: a stray key is almost always a typo, and dropping
                it silently is how a wrong prediction gets made.

        Returns:
            The values as floats, ordered by :attr:`features`.

        Raises:
            MissingFeatureError: If the row lacks a declared feature. The message
                lists what is missing **and** what was sent instead, because the
                two together are usually one typo.
            UnknownFeatureError: If ``strict`` and the row carries a feature the
                model does not declare.
            ValueError: If a value is not a number.
        """
        missing = [name for name in self.features if name not in row]
        extra = [name for name in row if name not in self.features]
        if missing:
            raise MissingFeatureError(missing, extra)
        if strict and extra:
            raise UnknownFeatureError(extra)
        return [_number(name, row[name]) for name in self.features]

    def label_of(self, index: int) -> str:
        """Name the class at an index.

        Args:
            index: The class index the model answered.

        Returns:
            The declared label, or the index as text when the manifest declares
            no classes — a regressor has none, and a classifier shipped without
            them is still usable.
        """
        if 0 <= index < len(self.classes):
            return self.classes[index]
        return str(index)


def manifest_from_dict(payload: Mapping[str, Any]) -> FeatureManifest:
    """Read a manifest out of a decoded JSON object.

    Args:
        payload: The decoded manifest.

    Returns:
        The :class:`FeatureManifest`.

    Raises:
        ManifestError: If the payload is not a mapping, or its ``features`` is
            not a list of strings.
    """
    if not isinstance(payload, Mapping):
        raise ManifestError("a manifest must be a JSON object")
    features = payload.get(FEATURES_KEY)
    if not isinstance(features, list) or not all(
        isinstance(name, str) for name in features
    ):
        raise ManifestError(
            f"{FEATURES_KEY!r} must be a list of strings naming the model's inputs"
        )
    return FeatureManifest(
        features=tuple(features),
        version=str(payload.get(VERSION_KEY, "")),
        outputs=tuple(_strings(payload.get(OUTPUTS_KEY))),
        classes=tuple(_strings(payload.get(CLASSES_KEY))),
    )


def manifest_from_json(text: str) -> FeatureManifest:
    """Read a manifest out of JSON text.

    Args:
        text: The manifest's JSON.

    Returns:
        The :class:`FeatureManifest`.

    Raises:
        ManifestError: If the text is not valid JSON, or not a valid manifest.
    """
    try:
        payload = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"the manifest is not valid JSON: {exc}") from exc
    return manifest_from_dict(payload)


def _strings(value: Any) -> list[str]:  # noqa: ANN401 — a manifest field is any JSON value
    """Read an optional list of strings out of a manifest field.

    Args:
        value: The raw field value.

    Returns:
        The strings it holds, empty when the field is absent or malformed.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _number(name: str, value: Any) -> float:  # noqa: ANN401 — a row value is any JSON value
    """Read one feature value as a float.

    Args:
        name: The feature's name, for the message.
        value: The value the row carried.

    Returns:
        The value as a float. ``bool`` passes as 0.0/1.0 because a one-hot flag
        is a legitimate feature.

    Raises:
        ValueError: If the value is not a number — a string where a number
            belongs would otherwise reach the model as whatever ``float()``
            guessed, or crash inside the runtime with no feature name attached.
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(
        f"feature {name!r} must be a number, got {type(value).__name__}: {value!r}"
    )
