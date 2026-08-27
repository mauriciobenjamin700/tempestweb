"""Inference over a sklearn model exported to ONNX, in the browser (R7).

The sibling of :mod:`tempestweb.vision`. Vision runs a model on pixels; this runs
one on a row of numbers — which is the commonest kind of ML in a business app:
a risk score, a demand forecast, a lead classification. Without it those had to
call an endpoint, which breaks offline-first, one of the framework's promises.

Example:
    ```python
    from tempestweb.tabular import TabularPredictor

    PREDICTOR = TabularPredictor("/models/risk.onnx", manifest="/models/risk.json")


    async def score(row: dict[str, float]) -> float:
        prediction = await PREDICTOR.predict(row)
        return prediction.score
    ```

The model is fetched through the shared asset cache, so it downloads once per
version rather than once per session.

!!! danger "The manifest is what keeps this from being silently wrong"
    An ONNX model is a function from an unlabelled vector to a number: the
    **order** carries all the meaning. Sending `{"idade": 30}` to a model trained
    on `age` does not fail — it reads a zero and answers a plausible, wrong
    score. With a manifest it raises
    :class:`~tempestweb.tabular.MissingFeatureError`, naming the feature that is
    missing and the one that was sent instead.

!!! info "Training and export are a build step, not a dependency"
    Exporting sklearn to ONNX runs in a throwaway environment
    (`uvx --from skl2onnx …`), documented in the recipe. Nothing here depends on
    sklearn, skl2onnx or numpy at runtime — those bounds would propagate to every
    tempestweb consumer for a step that happens once, on a developer's machine.

!!! warning "Modes A and B only"
    Mode C serves a fixed set of modules and refuses this import at build time.
"""

from __future__ import annotations

import base64
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from tempestweb.native import http as native_http
from tempestweb.native.onnx import OnnxModel, Tensor
from tempestweb.native.onnx import load as onnx_load
from tempestweb.native.onnx import run as onnx_run
from tempestweb.tabular.errors import PredictionError
from tempestweb.tabular.manifest import (
    FeatureManifest,
    manifest_from_dict,
    manifest_from_json,
)

__all__ = [
    "TabularPredictor",
    "Prediction",
    "DEFAULT_PROVIDERS",
    "FLOAT32",
]

#: Execution providers, in preference order. WASM only: the tabular models this
#: serves are small, and WebGPU's win does not pay for its kernel gaps.
DEFAULT_PROVIDERS = ["wasm"]

#: The element type a sklearn export expects for its input.
FLOAT32 = "float32"


@dataclass(frozen=True)
class Prediction:
    """One row's answer.

    Attributes:
        score: The single number the model answered. For a regressor this is the
            value; for a classifier it is the probability of the predicted class,
            or the raw output when the model reports no probabilities.
        label: The predicted class name, resolved through the manifest's
            ``classes``. Empty for a regressor.
        index: The predicted class index, or ``-1`` for a regressor.
        probabilities: Class name to probability, empty when the model does not
            report them.
    """

    score: float = 0.0
    label: str = ""
    index: int = -1
    probabilities: dict[str, float] = field(default_factory=dict)


class TabularPredictor:
    """A sklearn-to-ONNX model, loaded lazily and addressed by feature name.

    The session is created on the first prediction, not in ``__init__``: building
    a predictor at module scope must not download a model, and an app that
    defines three predictors and uses one should pay for one.

    Attributes:
        model_url: Where the ``.onnx`` file is served from.
        providers: Execution providers, in preference order.
    """

    def __init__(
        self,
        model_url: str,
        *,
        manifest: FeatureManifest | Mapping[str, object] | str,
        providers: Sequence[str] | None = None,
    ) -> None:
        """Describe a model without loading it.

        Args:
            model_url: Where the ``.onnx`` file is served from, same-origin in
                the artifact (``"/models/risk.onnx"``).
            manifest: The :class:`FeatureManifest`, a decoded manifest, or a URL
                to fetch one from. A URL is fetched on the first prediction,
                alongside the model.
            providers: Execution providers, in preference order.
        """
        self.model_url: str = model_url
        self.providers: list[str] = list(providers or DEFAULT_PROVIDERS)
        self._manifest_source: FeatureManifest | Mapping[str, object] | str = manifest
        self._manifest: FeatureManifest | None = None
        self._model: OnnxModel | None = None

    async def manifest(self) -> FeatureManifest:
        """Resolve the manifest, fetching it if it was given as a URL.

        Returns:
            The :class:`FeatureManifest`, cached after the first resolution.

        Raises:
            ManifestError: If the fetched document is not a valid manifest.
            NativeError: If the manifest URL cannot be fetched.
        """
        if self._manifest is not None:
            return self._manifest
        source = self._manifest_source
        if isinstance(source, FeatureManifest):
            self._manifest = source
        elif isinstance(source, str):
            response = await native_http.request("GET", source)
            self._manifest = manifest_from_json(response.text)
        else:
            self._manifest = manifest_from_dict(source)
        return self._manifest

    async def load(self) -> OnnxModel:
        """Create the inference session, or return the one already created.

        Returns:
            The :class:`~tempestweb.native.onnx.OnnxModel` handle.

        Raises:
            NativeError: If the model fails to download or compile
                (``model_load``).
        """
        if self._model is None:
            self._model = await onnx_load(self.model_url, providers=self.providers)
        return self._model

    async def predict(
        self, row: Mapping[str, object], *, strict: bool = True
    ) -> Prediction:
        """Score one row.

        Args:
            row: The feature values, in any order — the manifest imposes the one
                the model needs.
            strict: Whether a feature the model does not declare is an error.

        Returns:
            The :class:`Prediction`.

        Raises:
            MissingFeatureError: If the row lacks a declared feature.
            UnknownFeatureError: If ``strict`` and the row carries an undeclared
                one.
            PredictionError: If the model answers nothing readable.
            NativeError: If loading or inference fails.
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
        """Score several rows in a single inference run.

        One run rather than one per row: crossing the bridge and entering the
        runtime dominate the cost for a model this size, so a hundred rows scored
        together are far cheaper than a hundred scored apart.

        Args:
            rows: The rows to score.
            strict: Whether a feature the model does not declare is an error.

        Returns:
            One :class:`Prediction` per row, in order. An empty ``rows`` returns
            ``[]`` without loading the model — scoring nothing is valid.

        Raises:
            MissingFeatureError: If a row lacks a declared feature.
            UnknownFeatureError: If ``strict`` and a row carries an undeclared
                one.
            PredictionError: If the model answers nothing readable.
            NativeError: If loading or inference fails.
        """
        if not rows:
            return []
        manifest = await self.manifest()
        vectors = [manifest.vector(row, strict=strict) for row in rows]

        model = await self.load()
        tensor = _float_tensor(vectors)
        outputs = await onnx_run(model.session_id, {model.input_name: tensor})
        return _read_outputs(outputs, manifest, len(rows))


def _float_tensor(vectors: Sequence[Sequence[float]]) -> Tensor:
    """Pack rows into the float32 tensor a sklearn export expects.

    Built with :mod:`struct` rather than numpy on purpose: numpy is a `vision`
    extra, and a package that only ever packs a few dozen floats should not drag
    it — nor its bounds — into every consumer's resolution.

    Args:
        vectors: One row of feature values per prediction.

    Returns:
        The :class:`~tempestweb.native.onnx.Tensor`, shaped ``[rows, features]``.
    """
    flat = [value for vector in vectors for value in vector]
    raw = struct.pack(f"<{len(flat)}f", *flat)
    return Tensor(
        data_base64=base64.b64encode(raw).decode("ascii"),
        dims=[len(vectors), len(vectors[0])],
        dtype=FLOAT32,
    )


def _floats(tensor: Tensor) -> list[float]:
    """Unpack a tensor's raw bytes as a flat list of numbers.

    Args:
        tensor: The tensor to read.

    Returns:
        The values, empty when the element type is one this module does not
        unpack.
    """
    raw = base64.b64decode(tensor.data_base64)
    formats = {"float32": "f", "float64": "d", "int64": "q", "int32": "i"}
    code = formats.get(tensor.dtype)
    if code is None:
        return []
    size = struct.calcsize(code)
    count = len(raw) // size
    return [
        float(value) for value in struct.unpack(f"<{count}{code}", raw[: count * size])
    ]


def _read_outputs(
    outputs: Mapping[str, Tensor],
    manifest: FeatureManifest,
    rows: int,
) -> list[Prediction]:
    """Turn the model's raw outputs into one prediction per row.

    A sklearn export answers one of two shapes: a single output holding the
    prediction (a regressor), or a label output plus a probability output (a
    classifier). Both are read here, and neither is assumed — the manifest's
    ``outputs`` names them when it can, and the tensor shapes decide otherwise.

    Args:
        outputs: The model's outputs, by name.
        manifest: The manifest, for class labels and output names.
        rows: How many rows were scored.

    Returns:
        One :class:`Prediction` per row.

    Raises:
        PredictionError: If the outputs carry nothing readable.
    """
    if not outputs:
        raise PredictionError("the model answered no outputs")

    names = list(outputs)
    label_name = _pick(names, manifest.outputs, 0)
    probability_name = _pick(names, manifest.outputs, 1)

    labels = _floats(outputs[label_name]) if label_name else []
    probabilities = (
        _floats(outputs[probability_name])
        if probability_name and probability_name != label_name
        else []
    )
    if not labels and not probabilities:
        raise PredictionError(
            "the model's outputs could not be read as numbers: " + ", ".join(names)
        )

    width = len(probabilities) // rows if rows and probabilities else 0
    predictions: list[Prediction] = []
    for index in range(rows):
        row_probabilities = (
            probabilities[index * width : (index + 1) * width] if width else []
        )
        chosen = (
            int(labels[index])
            if index < len(labels)
            else (
                max(range(len(row_probabilities)), key=row_probabilities.__getitem__)
                if row_probabilities
                else -1
            )
        )
        score = (
            row_probabilities[chosen]
            if 0 <= chosen < len(row_probabilities)
            else (labels[index] if index < len(labels) else 0.0)
        )
        predictions.append(
            Prediction(
                score=score,
                label=manifest.label_of(chosen) if row_probabilities else "",
                index=chosen if row_probabilities else -1,
                probabilities={
                    manifest.label_of(position): value
                    for position, value in enumerate(row_probabilities)
                },
            )
        )
    return predictions


def _pick(names: Sequence[str], declared: Sequence[str], position: int) -> str:
    """Choose an output name, preferring what the manifest declared.

    Args:
        names: The output names the model actually answered.
        declared: The names the manifest declares, in order.
        position: Which declared name to take.

    Returns:
        The chosen name, or an empty string when there is none at that position.
    """
    if position < len(declared) and declared[position] in names:
        return declared[position]
    return names[position] if position < len(names) else ""
