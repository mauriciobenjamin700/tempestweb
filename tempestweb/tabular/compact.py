"""Tabular inference with **no inference runtime at all** (``.tmc``, #191).

:class:`~tempestweb.tabular.TabularPredictor` runs any sklearn export, and pays
``onnxruntime-web`` for it: **13.96 MB** of WebAssembly, 3.58 MB gzipped, measured
from what Chrome downloads. The model it runs is 660 bytes for a 30-feature
`LogisticRegression`. For an app whose only model is tabular, the runtime *is*
the download — +43% on the gzip of an offline Mode A artifact, and 12× a whole
Mode C one.

So this reader drops the runtime instead of the model. A linear model is a dot
product; a tree is a chain of comparisons. That is the entire implementation
below, in stdlib Python: :mod:`struct`, :mod:`array`, :mod:`math`.

Example:
    ```python
    from tempestweb.tabular import CompactPredictor

    PREDICTOR = CompactPredictor("/models/risk.tmc")


    async def score(row: dict[str, float]) -> float:
        prediction = await PREDICTOR.predict(row)
        return prediction.score
    ```

!!! info "The file carries its own manifest"
    ``export_sklearn_to_compact`` records ``feature_names`` and ``classes`` in
    the header, so a compact model needs no second file to be addressed by name.
    Pass ``manifest=`` only to override an export that recorded none.

!!! warning "It is a trade, not a replacement"
    ONNX covers every estimator; this covers **linear models and tree
    ensembles** — the two whose arithmetic fits here. Gradient boosting sums raw
    contributions through an init estimator, which is a different reader, and the
    exporter refuses it rather than writing something this would misread.

The writer is ``tempest_fastapi_sdk.modelops.export_sklearn_to_compact``, which
verifies the bytes against scikit-learn's own predictions and refuses to write a
file that disagrees. This reader is measured against files that writer produced,
with sklearn's answers beside them (``tests/fixtures/compact/``).

Layout (``TMC1``), as the writer documents it:

* bytes 0-3: the ASCII magic ``TMC1``;
* bytes 4-7: little-endian ``uint32``, the JSON header's length;
* the UTF-8 JSON header, space-padded so the first section starts on an 8-byte
  boundary;
* each section's raw little-endian values, in header order.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tempestweb.native import compact as native_compact
from tempestweb.tabular.errors import CompactFormatError, PredictionError
from tempestweb.tabular.manifest import (
    FeatureManifest,
    manifest_from_dict,
    manifest_from_json,
)
from tempestweb.tabular.predictor import Prediction

__all__ = [
    "COMPACT_MAGIC",
    "COMPACT_SCHEMA_VERSION",
    "CompactModel",
    "CompactPredictor",
    "parse",
]

#: Magic bytes opening every compact model file.
COMPACT_MAGIC = b"TMC1"

#: The layout version this reader implements. A file written for another one is
#: refused instead of guessed at: the sections are positional.
COMPACT_SCHEMA_VERSION = 1

#: Byte length of the magic plus the header-length field.
_PREFIX_LENGTH = 8

#: Array type codes per dtype the format uses, with their byte width.
_DTYPES: dict[str, tuple[str, int]] = {"float32": ("f", 4), "int32": ("i", 4)}

#: The ``kind`` values this reader knows how to score.
_KINDS = frozenset({"linear", "tree_ensemble"})

#: The ``link`` values this reader knows how to finish with.
_LINKS = frozenset({"softmax", "sigmoid", "normalize", "identity"})


@dataclass(frozen=True)
class CompactModel:
    """A parsed compact model: its header, and its arrays.

    Attributes:
        kind: ``"linear"`` or ``"tree_ensemble"`` — which reader scores it.
        task: ``"classification"`` or ``"regression"``.
        link: How raw scores become probabilities (``"softmax"``, ``"sigmoid"``,
            ``"normalize"``) or stay as they are (``"identity"``).
        classes: Class labels in score-column order. Empty for a regressor.
        class_type: How scikit-learn typed those labels (``"int"``, ``"float"``
            or ``"str"``), recorded by the exporter.
        n_features: Values expected per row.
        n_outputs: Score columns per row.
        n_trees: Trees in the ensemble; ``0`` for a linear model.
        estimator: Class name of the exported estimator, for messages.
        feature_names: The column order the model was trained on, when the
            export recorded it.
        offset: Per-feature offset of a folded scaler, empty when there is none.
        scale: Per-feature scale of a folded scaler, empty when there is none.
        sections: The decoded arrays, keyed by the name the header gave them.
    """

    kind: str
    task: str
    link: str
    classes: tuple[str, ...] = ()
    class_type: str = "str"
    n_features: int = 0
    n_outputs: int = 0
    n_trees: int = 0
    estimator: str = ""
    feature_names: tuple[str, ...] = ()
    offset: tuple[float, ...] = ()
    scale: tuple[float, ...] = ()
    sections: dict[str, Sequence[float]] = field(default_factory=dict)

    def manifest(self) -> FeatureManifest:
        """Build the manifest the file itself declares.

        Returns:
            The :class:`~tempestweb.tabular.FeatureManifest` over
            :attr:`feature_names` and :attr:`classes`.

        Raises:
            ManifestError: If the export recorded no feature names — the file
                can still be scored positionally, but not addressed by name.
        """
        return FeatureManifest(features=self.feature_names, classes=self.classes)

    def section(self, name: str) -> Sequence[float]:
        """Read one decoded section.

        Args:
            name: The section name the header gave it (e.g. ``"coef"``).

        Returns:
            Its values.

        Raises:
            CompactFormatError: If the model carries no such section.
        """
        try:
            return self.sections[name]
        except KeyError:
            raise CompactFormatError(
                f"a {self.kind} model needs the {name!r} section; "
                f"this file carries: {', '.join(sorted(self.sections)) or 'none'}"
            ) from None


def parse(data: bytes) -> CompactModel:
    """Read compact model bytes into a :class:`CompactModel`.

    Args:
        data: The whole ``.tmc`` file.

    Returns:
        The parsed model, arrays included.

    Raises:
        CompactFormatError: If the magic bytes, the layout version, the
            ``kind``/``link``, or a section's length do not hold.
    """
    if data[: len(COMPACT_MAGIC)] != COMPACT_MAGIC:
        raise CompactFormatError(
            "not a compact model file (magic was "
            f"{data[: len(COMPACT_MAGIC)]!r}, expected {COMPACT_MAGIC!r})"
        )
    (length,) = struct.unpack_from("<I", data, len(COMPACT_MAGIC))
    try:
        header = json.loads(
            data[_PREFIX_LENGTH : _PREFIX_LENGTH + length].decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CompactFormatError(f"the compact header is not JSON: {error}") from error
    if not isinstance(header, dict):
        raise CompactFormatError("the compact header is not a JSON object")

    version = header.get("schema_version")
    if version != COMPACT_SCHEMA_VERSION:
        raise CompactFormatError(
            f"compact schema {version} was written by another version of the "
            f"format; this reader implements {COMPACT_SCHEMA_VERSION}"
        )

    kind = str(header.get("kind", ""))
    if kind not in _KINDS:
        raise CompactFormatError(
            f"unsupported compact kind {kind!r}; this reader scores: "
            + ", ".join(sorted(_KINDS))
        )
    link = str(header.get("link", ""))
    if link not in _LINKS:
        raise CompactFormatError(
            f"unsupported compact link {link!r}; this reader applies: "
            + ", ".join(sorted(_LINKS))
        )

    sections = _sections(data, header, _PREFIX_LENGTH + length)
    preprocess = header.get("preprocess") or {}
    return CompactModel(
        kind=kind,
        task=str(header.get("task", "")),
        link=link,
        classes=tuple(str(value) for value in header.get("classes", ())),
        class_type=str(header.get("class_type", "str")),
        n_features=int(header.get("n_features", 0)),
        n_outputs=int(header.get("n_outputs", 0)),
        n_trees=int(header.get("n_trees", 0)),
        estimator=str(header.get("estimator", "")),
        feature_names=tuple(str(name) for name in header.get("feature_names", ())),
        offset=tuple(float(value) for value in preprocess.get("offset", ())),
        scale=tuple(float(value) for value in preprocess.get("scale", ())),
        sections=sections,
    )


class CompactPredictor:
    """A compact model, loaded lazily and addressed by feature name.

    The file is downloaded on the first prediction, not in ``__init__``: building
    a predictor at module scope must not fetch anything, and an app that defines
    three and uses one should pay for one.

    Attributes:
        model_url: Where the ``.tmc`` file is served from.
    """

    def __init__(
        self,
        model_url: str,
        *,
        manifest: FeatureManifest | Mapping[str, object] | str | None = None,
    ) -> None:
        """Describe a model without downloading it.

        Args:
            model_url: Where the ``.tmc`` file is served from, same-origin in the
                artifact (``"/models/risk.tmc"``).
            manifest: Overrides the feature order the file itself records. A
                :class:`~tempestweb.tabular.FeatureManifest`, a decoded manifest,
                or a URL to fetch one from. Leave it out for any export that
                recorded ``feature_names`` — which is every export that was
                given them.
        """
        self.model_url: str = model_url
        self._manifest_source: FeatureManifest | Mapping[str, object] | str | None = (
            manifest
        )
        self._manifest: FeatureManifest | None = None
        self._model: CompactModel | None = None

    async def load(self) -> CompactModel:
        """Download and parse the model, or return the one already parsed.

        Returns:
            The :class:`CompactModel`.

        Raises:
            CompactFormatError: If the bytes are not a compact model this reader
                understands.
            NativeError: If the file cannot be downloaded (``model_load``).
        """
        if self._model is None:
            self._model = parse(await native_compact.load(self.model_url))
        return self._model

    async def manifest(self) -> FeatureManifest:
        """Resolve the feature order, from the file or from the override.

        Returns:
            The :class:`~tempestweb.tabular.FeatureManifest`, cached after the
            first resolution.

        Raises:
            ManifestError: If neither the file nor the override declares
                features.
            NativeError: If a manifest URL cannot be fetched.
        """
        if self._manifest is not None:
            return self._manifest
        source = self._manifest_source
        if source is None:
            self._manifest = (await self.load()).manifest()
        elif isinstance(source, FeatureManifest):
            self._manifest = source
        elif isinstance(source, str):
            from tempestweb.native import http as native_http

            response = await native_http.request("GET", source)
            self._manifest = manifest_from_json(response.text)
        else:
            self._manifest = manifest_from_dict(source)
        return self._manifest

    async def predict(
        self, row: Mapping[str, object], *, strict: bool = True
    ) -> Prediction:
        """Score one row.

        Args:
            row: The feature values, in any order — the manifest imposes the one
                the model needs.
            strict: Whether a feature the model does not declare is an error.

        Returns:
            The :class:`~tempestweb.tabular.Prediction`.

        Raises:
            MissingFeatureError: If the row lacks a declared feature.
            UnknownFeatureError: If ``strict`` and the row carries an undeclared
                one.
            CompactFormatError: If the file is not a compact model this reader
                understands.
            PredictionError: If the model answers no rows.
            NativeError: If the download fails.
        """
        predictions = await self.predict_many([row], strict=strict)
        if not predictions:
            raise PredictionError("the model answered no rows")
        return predictions[0]

    async def predict_many(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        strict: bool = True,
    ) -> list[Prediction]:
        """Score several rows.

        Args:
            rows: The rows to score.
            strict: Whether a feature the model does not declare is an error.

        Returns:
            One :class:`~tempestweb.tabular.Prediction` per row, in order. An
            empty ``rows`` returns ``[]`` without downloading the model —
            scoring nothing is valid.

        Raises:
            MissingFeatureError: If a row lacks a declared feature.
            UnknownFeatureError: If ``strict`` and a row carries an undeclared
                one.
            CompactFormatError: If the file is not a compact model this reader
                understands.
            NativeError: If the download fails.
        """
        if not rows:
            return []
        manifest = await self.manifest()
        model = await self.load()
        vectors = [manifest.vector(row, strict=strict) for row in rows]
        scores = [_score(model, _preprocess(model, vector)) for vector in vectors]
        return [_finish(model, manifest, row_scores) for row_scores in scores]


def _sections(
    data: bytes, header: Mapping[str, Any], start: int
) -> dict[str, Sequence[float]]:
    """Decode every section the header promises.

    Args:
        data: The whole file.
        header: The parsed header.
        start: Byte offset the first section starts at.

    Returns:
        The arrays, keyed by section name.

    Raises:
        CompactFormatError: If a dtype is unknown, or the file ends before a
            section the header declared.
    """
    decoded: dict[str, Sequence[float]] = {}
    cursor = start
    for section in header.get("sections", ()):
        name = str(section.get("name", ""))
        dtype = str(section.get("dtype", ""))
        count = int(section.get("length", 0))
        if dtype not in _DTYPES:
            raise CompactFormatError(
                f"section {name!r} uses dtype {dtype!r}; this reader decodes: "
                + ", ".join(sorted(_DTYPES))
            )
        code, width = _DTYPES[dtype]
        end = cursor + count * width
        if end > len(data):
            raise CompactFormatError(
                f"section {name!r} runs past the end of the file "
                f"(needs {count * width} bytes, {len(data) - cursor} remain)"
            )
        values = array(code)
        values.frombytes(data[cursor:end])
        if sys.byteorder == "big":
            values.byteswap()
        decoded[name] = values
        cursor = end
    return decoded


def _preprocess(model: CompactModel, vector: Sequence[float]) -> list[float]:
    """Apply the scaler the exporter folded into the header, if any.

    Args:
        model: The parsed model.
        vector: The row, ordered by the manifest.

    Returns:
        The row the model's own arithmetic expects.
    """
    if not model.scale:
        return list(vector)
    return [
        (value - offset) / (scale or 1.0)
        for value, offset, scale in zip(vector, model.offset, model.scale, strict=False)
    ]


def _score(model: CompactModel, vector: Sequence[float]) -> list[float]:
    """Produce the raw score columns for one row.

    Args:
        model: The parsed model.
        vector: The preprocessed row.

    Returns:
        One score per output column.

    Raises:
        CompactFormatError: If a section the reader needs is absent.
    """
    if model.kind == "linear":
        return _score_linear(model, vector)
    return _score_trees(model, vector)


def _score_linear(model: CompactModel, vector: Sequence[float]) -> list[float]:
    """Dot the row against every output's coefficients.

    Args:
        model: The parsed model.
        vector: The preprocessed row.

    Returns:
        One score per output column.

    Raises:
        CompactFormatError: If ``coef`` or ``intercept`` is absent.
    """
    coefficients = model.section("coef")
    intercepts = model.section("intercept")
    features = model.n_features
    return [
        math.fsum(
            coefficients[output * features + index] * value
            for index, value in enumerate(vector)
        )
        + intercepts[output]
        for output in range(model.n_outputs)
    ]


def _score_trees(model: CompactModel, vector: Sequence[float]) -> list[float]:
    """Walk every tree and average the leaves they land on.

    The comparison happens in **float32**, because that is what scikit-learn
    does: ``sklearn.tree`` casts its input to float32 before traversing, so a
    threshold stored as 5.099999904632568 and an input of 5.1 compare *equal*
    there and go left. Comparing in float64 sends that row right instead, and one
    tree in a forest then answers a different leaf.

    Leaves are packed rather than stored per node: a leaf's ``node_feature``
    entry holds ``-1 - slot``, so the sign tells leaf from split and the value
    finds its own row in ``leaf_value``.

    Args:
        model: The parsed model.
        vector: The preprocessed row.

    Returns:
        One averaged score per output column.

    Raises:
        CompactFormatError: If a node section is absent.
    """
    features = model.section("node_feature")
    thresholds = model.section("node_threshold")
    lefts = model.section("node_left")
    rights = model.section("node_right")
    leaves = model.section("leaf_value")
    offsets = model.section("tree_offset")

    outputs = model.n_outputs
    routed = [_as_float32(value) for value in vector]
    totals = [0.0] * outputs
    trees = len(offsets) - 1
    for tree in range(trees):
        node = int(offsets[tree])
        while features[node] >= 0:
            index = int(features[node])
            node = int(
                lefts[node] if routed[index] <= thresholds[node] else rights[node]
            )
        slot = -1 - int(features[node])
        base = slot * outputs
        for output in range(outputs):
            totals[output] += leaves[base + output]
    return [total / trees for total in totals] if trees else totals


def _finish(
    model: CompactModel, manifest: FeatureManifest, scores: Sequence[float]
) -> Prediction:
    """Turn raw scores into the answer, through the model's link function.

    Args:
        model: The parsed model.
        manifest: The resolved feature manifest, which names the classes.
        scores: One raw score per output column.

    Returns:
        The :class:`~tempestweb.tabular.Prediction`.
    """
    if model.link == "identity":
        return Prediction(score=float(scores[0]) if scores else 0.0)

    if model.link == "sigmoid":
        positive = _sigmoid(float(scores[0]))
        probabilities = [1.0 - positive, positive]
    elif model.link == "softmax":
        largest = max(scores)
        exponentiated = [math.exp(value - largest) for value in scores]
        total = math.fsum(exponentiated)
        probabilities = [value / total for value in exponentiated]
    else:
        total = math.fsum(scores)
        divisor = total if total else 1.0
        probabilities = [value / divisor for value in scores]

    index = max(range(len(probabilities)), key=probabilities.__getitem__)
    labels = model.classes or manifest.classes
    label = labels[index] if index < len(labels) else str(index)
    return Prediction(
        score=probabilities[index],
        label=label,
        index=index,
        probabilities={
            (labels[position] if position < len(labels) else str(position)): value
            for position, value in enumerate(probabilities)
        },
    )


def _sigmoid(value: float) -> float:
    """Map one raw score to a probability, saturating instead of overflowing.

    Written the stable way, for the same reason the softmax beside it subtracts
    the largest score: ``1 / (1 + exp(-x))`` raises ``OverflowError`` once ``x``
    goes below about -709 in float64, and a score that far out is exactly what an
    app that sends a feature in the wrong unit produces (grams where the model
    was trained on kilograms reaches -908 on this repository's own fixture). The
    honest answer there is a probability of zero, not a crash. So the branch that
    would exponentiate a large positive number exponentiates a large negative one
    instead, which underflows to 0.0 harmlessly.

    Args:
        value: The raw score of the positive class.

    Returns:
        The probability of the positive class, in ``[0.0, 1.0]``.
    """
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponentiated = math.exp(value)
    return exponentiated / (1.0 + exponentiated)


def _as_float32(value: float) -> float:
    """Round a value to the float32 scikit-learn would have compared.

    Args:
        value: The feature value.

    Returns:
        The same value narrowed to float32 precision.
    """
    return float(struct.unpack("<f", struct.pack("<f", value))[0])
