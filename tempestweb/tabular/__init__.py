"""Tabular inference in the browser — the sibling of `tempestweb.vision`.

Vision runs a model on pixels. This runs one on a **row of numbers**, which is
the commonest kind of ML in a business app: a risk score, a demand forecast, a
lead classification. Without it, those had to call an endpoint — which breaks
offline-first, one of the framework's promises.

**Modules**

    * :mod:`manifest` — which features the model expects, and in what order.
    * :mod:`predictor` — `TabularPredictor`, loaded lazily, addressed by name.
    * :mod:`errors` — one named error per way a row can fail to match.

Example:
    ```python
    from tempestweb.tabular import TabularPredictor

    PREDICTOR = TabularPredictor("/models/risk.onnx", manifest="/models/risk.json")

    prediction = await PREDICTOR.predict({"age": 30, "income": 3200.0})
    print(prediction.score, prediction.label, prediction.probabilities)
    ```

!!! danger "The manifest is what keeps this from being silently wrong"
    An ONNX model is a function from an unlabelled vector of floats to a number:
    the **order** carries all the meaning, and nothing in the runtime checks it.
    An app that sends `{"idade": 30}` to a model trained on `age` does not fail —
    it reads a zero where the age should be and answers a plausible, wrong score,
    and nothing downstream can tell.

    With a manifest that raises `MissingFeatureError`, naming the feature that is
    missing **and** the one that was sent instead, because the two together are
    usually one typo.

!!! info "Training and export are a build step, not a dependency"
    Exporting sklearn to ONNX runs in a throwaway environment
    (`uvx --from skl2onnx …`), documented in the recipe. Nothing here depends on
    sklearn, skl2onnx or numpy at runtime: those bounds would propagate to every
    tempestweb consumer for a step that happens once, on a developer's machine.

!!! warning "Modes A and B only"
    Mode C serves a fixed set of modules — `tempest_core`, `tempestweb.components`
    and `tempestweb.native` — and refuses this import at build time.

Import everything from this package level rather than from submodules.
"""

from __future__ import annotations

from tempestweb.tabular.errors import (
    ManifestError,
    MissingFeatureError,
    PredictionError,
    TabularError,
    UnknownFeatureError,
)
from tempestweb.tabular.manifest import (
    CLASSES_KEY,
    FEATURES_KEY,
    OUTPUTS_KEY,
    VERSION_KEY,
    FeatureManifest,
    manifest_from_dict,
    manifest_from_json,
)
from tempestweb.tabular.predictor import (
    DEFAULT_PROVIDERS,
    FLOAT32,
    Prediction,
    TabularPredictor,
)

__all__ = [
    "TabularPredictor",
    "Prediction",
    "FeatureManifest",
    "manifest_from_dict",
    "manifest_from_json",
    "TabularError",
    "ManifestError",
    "MissingFeatureError",
    "UnknownFeatureError",
    "PredictionError",
    "DEFAULT_PROVIDERS",
    "FLOAT32",
    "FEATURES_KEY",
    "VERSION_KEY",
    "OUTPUTS_KEY",
    "CLASSES_KEY",
]
