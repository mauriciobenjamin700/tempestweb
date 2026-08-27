"""The compact reader, measured against scikit-learn's own answers.

A format has two halves, and the expensive failure is the silent one: a reader
that walks a tree slightly differently than scikit-learn does agrees on almost
every row and disagrees on the one where a threshold sits exactly on a float32
boundary. So none of the fixtures here are written by this repository. The
``.tmc`` files come from the format's publisher —
``tempest_fastapi_sdk.modelops.export_sklearn_to_compact``, which refuses to
write a file that disagrees with the estimator — and beside them sits what
**scikit-learn itself** answered for the same rows
(``tests/conformance/_compact_models.py`` regenerates both).

`test_every_fixture_matches_sklearn_label_for_label` is the test this file exists
for. The rest keep the failure modes named: a file from another version of the
format refused rather than guessed at, a missing feature caught before the dot
product, a scaler folded rather than ignored.
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

import pytest

from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.tabular import (
    COMPACT_MAGIC,
    COMPACT_SCHEMA_VERSION,
    CompactFormatError,
    CompactPredictor,
    FeatureManifest,
    MissingFeatureError,
    UnknownFeatureError,
    parse,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODELS = FIXTURES / "compact"
EXPECTATIONS: dict[str, Any] = json.loads(
    (FIXTURES / "compact_expectations.json").read_text(encoding="utf-8")
)

#: Largest probability difference accepted against scikit-learn. The exporter
#: verifies at 1e-5 and records what it saw; this reader does the same float32
#: arithmetic, so anything above rounding means the format lost information.
TOLERANCE = 1e-6


class ModelBridge:
    """A fake bridge serving a fixture's bytes to ``compact.load``."""

    def __init__(self, data: bytes) -> None:
        self.data: bytes = data
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        return {
            "ok": True,
            "value": {
                "bytes": base64.b64encode(self.data).decode("ascii"),
                "size": len(self.data),
            },
        }


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


def _model_bytes(name: str) -> bytes:
    """Read one fixture model."""
    return (MODELS / f"{name}.tmc").read_bytes()


def _predictor(name: str, **kwargs: Any) -> tuple[CompactPredictor, ModelBridge]:
    """Build a predictor served by a bridge holding that fixture."""
    bridge = ModelBridge(_model_bytes(name))
    install_bridge(bridge)
    return CompactPredictor(f"/models/{name}.tmc", **kwargs), bridge


# --------------------------------------------------------------------------
# Parity: the reader against scikit-learn, over every fixture
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
@pytest.mark.asyncio
async def test_every_fixture_matches_sklearn_label_for_label(name: str) -> None:
    expected = EXPECTATIONS[name]
    predictor, _ = _predictor(name)

    predictions = await predictor.predict_many(expected["rows"])

    assert len(predictions) == len(expected["rows"])
    if expected["task"] == "regression":
        for prediction, answer in zip(predictions, expected["labels"], strict=True):
            assert prediction.score == pytest.approx(float(answer), abs=1e-4)
            assert prediction.label == ""
            assert prediction.index == -1
        return

    assert [prediction.label for prediction in predictions] == expected["labels"]
    for prediction, answer in zip(predictions, expected["probabilities"], strict=True):
        for index, probability in enumerate(answer):
            label = expected["classes"][index]
            assert prediction.probabilities[label] == pytest.approx(
                probability, abs=TOLERANCE
            )


@pytest.mark.asyncio
async def test_a_row_is_ordered_by_name_so_the_caller_never_remembers_the_order() -> (
    None
):
    expected = EXPECTATIONS["linear_binary_sigmoid"]
    row = expected["rows"][0]
    shuffled = dict(reversed(list(row.items())))
    predictor, _ = _predictor("linear_binary_sigmoid")

    ordered = await predictor.predict(row)
    reversed_order = await predictor.predict(shuffled)

    assert ordered.label == reversed_order.label
    assert ordered.score == pytest.approx(reversed_order.score)


@pytest.mark.asyncio
async def test_the_file_carries_its_own_manifest() -> None:
    expected = EXPECTATIONS["forest_classifier_normalize"]
    predictor, _ = _predictor("forest_classifier_normalize")

    manifest = await predictor.manifest()

    assert list(manifest.features) == expected["features"]
    assert list(manifest.classes) == expected["classes"]


@pytest.mark.asyncio
async def test_a_scaler_step_is_folded_rather_than_dropped() -> None:
    model = parse(_model_bytes("pipeline_scaler_linear"))

    assert model.estimator == "LogisticRegression"
    assert len(model.scale) == model.n_features
    assert any(value != 1.0 for value in model.scale)


# --------------------------------------------------------------------------
# The link function: saturating rather than raising
# --------------------------------------------------------------------------


#: A row of the fixture's six features with every value in the wrong unit — the
#: mistake an app makes when it sends grams to a model trained on kilograms. Its
#: raw score is -908.29, and negating it gives +952.45: both past the ±709 where
#: ``math.exp`` overflows float64.
WRONG_UNIT_ROW: dict[str, float] = {
    "mean radius": 50.0,
    "mean texture": 60.0,
    "mean perimeter": 400.0,
    "mean area": 4000.0,
    "mean smoothness": 0.3,
    "mean compactness": 1000.0,
}


@pytest.mark.asyncio
async def test_a_score_far_off_the_scale_saturates_instead_of_overflowing() -> None:
    """A wrong-unit row is a probability of 0 or 1, not an OverflowError.

    ``1 / (1 + exp(-x))`` raises ``OverflowError: math range error`` below about
    -709, so before the stable form this crashed rather than answering — while
    the softmax beside it had subtracted the largest score all along.
    """
    predictor, _ = _predictor("linear_binary_sigmoid")

    low = await predictor.predict(WRONG_UNIT_ROW)
    high = await predictor.predict(
        {name: -value for name, value in WRONG_UNIT_ROW.items()}
    )

    assert low.label == "0"
    assert low.probabilities == {"0": 1.0, "1": 0.0}
    assert high.label == "1"
    assert high.probabilities == {"0": 0.0, "1": 1.0}


# --------------------------------------------------------------------------
# Loading: once, lazily, and only when there is a row to score
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_model_is_downloaded_once_and_reused() -> None:
    expected = EXPECTATIONS["linear_binary_sigmoid"]
    predictor, bridge = _predictor("linear_binary_sigmoid")

    await predictor.predict(expected["rows"][0])
    await predictor.predict(expected["rows"][1])

    assert len(bridge.calls) == 1


@pytest.mark.asyncio
async def test_scoring_no_rows_downloads_nothing() -> None:
    predictor, bridge = _predictor("linear_binary_sigmoid")

    assert await predictor.predict_many([]) == []
    assert bridge.calls == []


@pytest.mark.asyncio
async def test_an_override_manifest_wins_over_the_one_in_the_file() -> None:
    expected = EXPECTATIONS["linear_binary_sigmoid"]
    renamed = [f"f{index}" for index in range(len(expected["features"]))]
    predictor, _ = _predictor(
        "linear_binary_sigmoid",
        manifest=FeatureManifest(features=tuple(renamed), classes=("0", "1")),
    )
    source = expected["rows"][0]
    row = {
        alias: source[feature]
        for alias, feature in zip(renamed, expected["features"], strict=True)
    }

    prediction = await predictor.predict(row)

    assert prediction.label == expected["labels"][0]


# --------------------------------------------------------------------------
# The mismatch that is otherwise silent
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_renamed_feature_raises_naming_both_halves() -> None:
    expected = EXPECTATIONS["linear_binary_sigmoid"]
    row = dict(expected["rows"][0])
    declared = expected["features"][0]
    row["typo"] = row.pop(declared)
    predictor, _ = _predictor("linear_binary_sigmoid")

    with pytest.raises(MissingFeatureError) as raised:
        await predictor.predict(row)

    assert declared in str(raised.value)
    assert "typo" in str(raised.value)


@pytest.mark.asyncio
async def test_an_undeclared_feature_is_an_error_unless_it_is_waived() -> None:
    expected = EXPECTATIONS["linear_binary_sigmoid"]
    row = dict(expected["rows"][0]) | {"unrelated": 1.0}
    predictor, _ = _predictor("linear_binary_sigmoid")

    with pytest.raises(UnknownFeatureError):
        await predictor.predict(row)

    assert (await predictor.predict(row, strict=False)).label == expected["labels"][0]


# --------------------------------------------------------------------------
# The format: refused rather than guessed at
# --------------------------------------------------------------------------


def test_bytes_that_are_not_a_compact_model_are_refused_by_name() -> None:
    with pytest.raises(CompactFormatError) as raised:
        parse(b"ONNX" + b"\x00" * 32)

    assert "TMC1" in str(raised.value)


def test_a_file_from_another_version_of_the_format_is_refused() -> None:
    data = bytearray(_model_bytes("linear_binary_sigmoid"))
    (length,) = struct.unpack_from("<I", data, 4)
    header = json.loads(data[8 : 8 + length].decode("utf-8"))
    header["schema_version"] = COMPACT_SCHEMA_VERSION + 1
    rewritten = json.dumps(header, separators=(",", ":")).encode("utf-8")
    rewritten += b" " * (length - len(rewritten))
    data[8 : 8 + length] = rewritten

    with pytest.raises(CompactFormatError) as raised:
        parse(bytes(data))

    assert str(COMPACT_SCHEMA_VERSION) in str(raised.value)


def test_a_truncated_file_names_the_section_that_ran_out() -> None:
    data = _model_bytes("forest_classifier_normalize")

    with pytest.raises(CompactFormatError) as raised:
        parse(data[: len(data) - 64])

    assert "past the end of the file" in str(raised.value)


def test_the_magic_is_the_one_the_writer_documents() -> None:
    assert COMPACT_MAGIC == b"TMC1"
    assert _model_bytes("linear_binary_sigmoid")[:4] == COMPACT_MAGIC


def test_a_parsed_model_reports_what_the_exporter_recorded() -> None:
    for name, expected in EXPECTATIONS.items():
        model = parse(_model_bytes(name))
        assert model.kind == expected["kind"]
        assert model.task == expected["task"]
        assert list(model.feature_names) == expected["features"]
        assert list(model.classes) == expected["classes"]
        assert (MODELS / f"{name}.tmc").stat().st_size == expected["size_bytes"]
