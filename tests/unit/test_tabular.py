"""Tabular inference: the manifest, and the mismatch that is otherwise silent.

The case this package exists for is
`test_a_renamed_feature_raises_naming_both_halves`. An ONNX model is a function
from an unlabelled vector of floats to a number, so the **order** carries all the
meaning and nothing in the runtime checks it. A row written `{"idade": 30}` for a
model trained on `age` does not fail — it reads a zero where the age should be
and answers a plausible, wrong score. Nothing downstream can tell.

Every other test here exists to keep that guarantee honest: order imposed by the
manifest rather than remembered, a duplicate feature refused at build time, a
non-number refused with the feature's name attached.
"""

from __future__ import annotations

import base64
import json
import struct
from typing import Any

import pytest

from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.tabular import (
    FeatureManifest,
    ManifestError,
    MissingFeatureError,
    Prediction,
    PredictionError,
    TabularPredictor,
    UnknownFeatureError,
    manifest_from_dict,
    manifest_from_json,
)

MANIFEST = FeatureManifest(
    features=("age", "income", "tenure_months"),
    version="2026-08-27",
    outputs=("label", "probabilities"),
    classes=("low", "high"),
)

ROW = {"age": 30, "income": 3200.0, "tenure_months": 18}


def _tensor(
    values: list[float], dims: list[int], dtype: str = "float32"
) -> dict[str, Any]:
    """Build a wire tensor carrying ``values``."""
    code = {"float32": "f", "int64": "q"}[dtype]
    packed = [int(v) for v in values] if code == "q" else list(values)
    raw = struct.pack(f"<{len(values)}{code}", *packed)
    return {
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "dims": dims,
        "dtype": dtype,
    }


class ScriptedBridge:
    """A fake bridge answering scripted values, recording every envelope."""

    def __init__(self, script: list[Any]) -> None:
        self.script: list[Any] = script
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"ok": True, "value": outcome}


def _session(rows: int = 1) -> list[Any]:
    """Script a load plus a classifier run answering ``rows`` predictions."""
    labels = [1.0] * rows
    probabilities = [0.2, 0.8] * rows
    return [
        {
            "session_id": "s1",
            "input_names": ["float_input"],
            "output_names": ["label", "probabilities"],
        },
        {
            "outputs": {
                "label": _tensor(labels, [rows], "int64"),
                "probabilities": _tensor(probabilities, [rows, 2]),
            }
        },
    ]


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


# --------------------------------------------------------------------------
# The manifest: the order is the contract
# --------------------------------------------------------------------------


def test_the_manifest_imposes_the_order_so_the_caller_never_remembers_it() -> None:
    assert MANIFEST.vector({"income": 3200.0, "tenure_months": 18, "age": 30}) == [
        30.0,
        3200.0,
        18.0,
    ]


def test_a_renamed_feature_raises_naming_both_halves() -> None:
    """The whole point: `{"idade": 30}` against a model trained on `age`."""
    with pytest.raises(MissingFeatureError) as caught:
        MANIFEST.vector({"idade": 30, "income": 3200.0, "tenure_months": 18})

    assert caught.value.missing == ("age",)
    assert caught.value.extra == ("idade",)
    assert "age" in str(caught.value)
    assert "idade" in str(caught.value)


def test_a_feature_simply_left_out_raises_too() -> None:
    with pytest.raises(MissingFeatureError) as caught:
        MANIFEST.vector({"age": 30, "income": 3200.0})
    assert caught.value.missing == ("tenure_months",)


def test_an_extra_feature_is_an_error_by_default() -> None:
    """A stray key is almost always a typo; dropping it makes a wrong score."""
    with pytest.raises(UnknownFeatureError) as caught:
        MANIFEST.vector({**ROW, "renda": 999})
    assert caught.value.unknown == ("renda",)


def test_an_extra_feature_can_be_tolerated_on_request() -> None:
    assert MANIFEST.vector({**ROW, "renda": 999}, strict=False) == [30.0, 3200.0, 18.0]


def test_a_value_that_is_not_a_number_names_the_feature() -> None:
    with pytest.raises(ValueError, match="income"):
        MANIFEST.vector({**ROW, "income": "muito"})


def test_a_boolean_is_a_legitimate_one_hot_feature() -> None:
    manifest = FeatureManifest(features=("active",))
    assert manifest.vector({"active": True}) == [1.0]
    assert manifest.vector({"active": False}) == [0.0]


def test_a_manifest_with_no_features_is_refused() -> None:
    with pytest.raises(ManifestError, match="at least one feature"):
        FeatureManifest(features=())


def test_a_manifest_that_declares_a_feature_twice_is_refused() -> None:
    """A duplicate makes the order ambiguous — the one thing it must not be."""
    with pytest.raises(ManifestError, match="twice"):
        FeatureManifest(features=("age", "income", "age"))


def test_a_manifest_reads_from_a_decoded_object() -> None:
    manifest = manifest_from_dict(
        {"features": ["a", "b"], "version": "7", "classes": ["no", "yes"]}
    )
    assert manifest.features == ("a", "b")
    assert manifest.version == "7"
    assert manifest.classes == ("no", "yes")


def test_a_manifest_reads_from_json_text() -> None:
    manifest = manifest_from_json(json.dumps({"features": ["a"], "version": "1"}))
    assert manifest.features == ("a",)


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        json.dumps([1, 2]),
        json.dumps({"features": "age"}),
        json.dumps({"features": [1, 2]}),
        json.dumps({}),
    ],
)
def test_a_malformed_manifest_is_refused_loudly(payload: str) -> None:
    with pytest.raises(ManifestError):
        manifest_from_json(payload)


def test_a_class_index_resolves_to_its_label_and_degrades_to_the_index() -> None:
    assert MANIFEST.label_of(1) == "high"
    assert MANIFEST.label_of(9) == "9"
    assert FeatureManifest(features=("a",)).label_of(0) == "0"


# --------------------------------------------------------------------------
# The predictor
# --------------------------------------------------------------------------


async def test_a_classifier_row_is_scored_and_labelled() -> None:
    install_bridge(ScriptedBridge(_session()))
    predictor = TabularPredictor("/models/risk.onnx", manifest=MANIFEST)

    prediction = await predictor.predict(ROW)

    assert prediction.index == 1
    assert prediction.label == "high"
    assert prediction.score == pytest.approx(0.8)
    assert prediction.probabilities == {
        "low": pytest.approx(0.2),
        "high": pytest.approx(0.8),
    }


async def test_the_row_reaches_the_model_in_the_manifest_order() -> None:
    bridge = ScriptedBridge(_session())
    install_bridge(bridge)

    await TabularPredictor("/models/risk.onnx", manifest=MANIFEST).predict(
        {"tenure_months": 18, "age": 30, "income": 3200.0}
    )

    feeds = bridge.calls[1]["args"]["feeds"]["float_input"]
    raw = base64.b64decode(feeds["data_base64"])
    assert list(struct.unpack("<3f", raw)) == [30.0, 3200.0, 18.0]
    assert feeds["dims"] == [1, 3]
    assert feeds["dtype"] == "float32"


async def test_the_model_is_not_loaded_until_the_first_prediction() -> None:
    """Building a predictor at module scope must not download a model."""
    bridge = ScriptedBridge(_session())
    install_bridge(bridge)

    predictor = TabularPredictor("/models/risk.onnx", manifest=MANIFEST)
    assert bridge.calls == []

    await predictor.predict(ROW)
    assert bridge.calls[0]["capability"] == "onnx.load"


async def test_the_session_is_reused_across_predictions() -> None:
    bridge = ScriptedBridge(
        [*_session(), {"outputs": {"label": _tensor([0.0], [1], "int64")}}]
    )
    install_bridge(bridge)
    predictor = TabularPredictor("/models/risk.onnx", manifest=MANIFEST)

    await predictor.predict(ROW)
    await predictor.predict(ROW)

    loads = [c for c in bridge.calls if c["capability"] == "onnx.load"]
    assert len(loads) == 1


async def test_several_rows_are_scored_in_one_run() -> None:
    bridge = ScriptedBridge(_session(rows=3))
    install_bridge(bridge)

    predictions = await TabularPredictor(
        "/models/risk.onnx", manifest=MANIFEST
    ).predict_many([ROW, ROW, ROW])

    runs = [c for c in bridge.calls if c["capability"] == "onnx.run"]
    assert len(runs) == 1
    assert len(predictions) == 3
    assert all(p.label == "high" for p in predictions)


async def test_scoring_no_rows_returns_empty_without_loading_anything() -> None:
    bridge = ScriptedBridge([])
    install_bridge(bridge)

    assert await TabularPredictor("/m.onnx", manifest=MANIFEST).predict_many([]) == []
    assert bridge.calls == []


async def test_a_regressor_answers_a_value_with_no_label() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {
                    "session_id": "s1",
                    "input_names": ["X"],
                    "output_names": ["variable"],
                },
                {"outputs": {"variable": _tensor([0.42], [1, 1])}},
            ]
        )
    )
    manifest = FeatureManifest(features=("age", "income", "tenure_months"))

    prediction = await TabularPredictor("/m.onnx", manifest=manifest).predict(ROW)

    assert prediction.score == pytest.approx(0.42)
    assert prediction.label == ""
    assert prediction.index == -1
    assert prediction.probabilities == {}


async def test_a_mismatch_is_caught_before_the_model_is_even_loaded() -> None:
    """The cheap check comes first: no download to discover a typo."""
    bridge = ScriptedBridge(_session())
    install_bridge(bridge)

    with pytest.raises(MissingFeatureError):
        await TabularPredictor("/m.onnx", manifest=MANIFEST).predict({"idade": 30})

    assert bridge.calls == []


async def test_a_manifest_url_is_fetched_once() -> None:
    manifest_json = json.dumps({"features": ["age"], "classes": ["no", "yes"]})
    bridge = ScriptedBridge(
        [
            {"status": 200, "ok": True, "text": manifest_json},
            *_session(),
            {"outputs": {"label": _tensor([0.0], [1], "int64")}},
        ]
    )
    install_bridge(bridge)
    predictor = TabularPredictor("/m.onnx", manifest="/models/risk.json")

    await predictor.predict({"age": 30})
    await predictor.predict({"age": 31})

    fetches = [c for c in bridge.calls if c["capability"] == "http.request"]
    assert len(fetches) == 1
    assert fetches[0]["args"]["url"] == "/models/risk.json"


async def test_a_model_that_answers_nothing_raises_a_named_error() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {"session_id": "s1", "input_names": ["X"], "output_names": []},
                {"outputs": {}},
            ]
        )
    )

    with pytest.raises(PredictionError):
        await TabularPredictor("/m.onnx", manifest=MANIFEST).predict(ROW)


async def test_an_output_of_an_unreadable_type_raises_rather_than_guessing() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {"session_id": "s1", "input_names": ["X"], "output_names": ["out"]},
                {
                    "outputs": {
                        "out": {"data_base64": "AQID", "dims": [1], "dtype": "string"}
                    }
                },
            ]
        )
    )

    with pytest.raises(PredictionError):
        await TabularPredictor("/m.onnx", manifest=MANIFEST).predict(ROW)


async def test_the_providers_reach_the_load_call() -> None:
    bridge = ScriptedBridge(_session())
    install_bridge(bridge)

    await TabularPredictor(
        "/m.onnx", manifest=MANIFEST, providers=["webgpu", "wasm"]
    ).predict(ROW)

    assert bridge.calls[0]["args"]["providers"] == ["webgpu", "wasm"]


def test_a_prediction_is_frozen_because_it_is_an_answer() -> None:
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        Prediction(score=1.0).score = 2.0  # type: ignore[misc]


def test_mode_c_refuses_the_import_with_a_named_error() -> None:
    from tempestweb.transpile import TranspileError, generate

    source = (
        "from dataclasses import dataclass, field\n"
        "from tempest_core import App, Column, Text, Widget\n"
        "from tempestweb.tabular import TabularPredictor\n"
        "@dataclass\n"
        "class State:\n"
        "    rows: list[str] = field(default_factory=list)\n"
        "def view(app: App[State]) -> Widget:\n"
        '    return Column(key="b", children=[Text(key="t", content="hi")])\n'
    )
    with pytest.raises(TranspileError) as caught:
        generate(source, filename="app.py")

    assert "tempestweb.tabular" in str(caught.value)
