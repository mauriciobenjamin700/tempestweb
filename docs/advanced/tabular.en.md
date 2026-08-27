# Tabular inference in the browser (`tempestweb.tabular`)

!!! tip "What you'll learn"
    How to run a sklearn model **inside the browser**, over a row of numbers — a
    risk score, a demand forecast, a lead classification — without calling an
    endpoint and without breaking offline-first. 🧮

tempestweb already had `vision/`: `Classifier`/`Detector`/`Segmenter` over ONNX,
with the model running in the browser. For **tabular** data — the commonest kind
of ML in a business app — there was nothing, and the app had to call an endpoint.

## The problem the manifest solves

An ONNX model is a function from an **unlabelled vector of floats** to a number.
The **order** carries all the meaning, and nothing in the runtime checks it:

```python
# ❌ Without a manifest this does not fail. It answers a plausible, wrong number.
await session.run({"X": [[30.0, 3200.0, 18.0]]})   # age, income, tenure? or income, age, tenure?
```

An app sending `{"idade": 30}` to a model trained on `age` reads a zero where the
age should be — and nothing downstream can tell.

```json
{
  "version": "2026-08-27",
  "features": ["age", "income", "tenure_months"],
  "outputs": ["label", "probabilities"],
  "classes": ["low", "high"]
}
```

With the manifest next to the `.onnx`, that same mistake becomes a message:

```text
MissingFeatureError: row is missing 1 feature(s): age;
it carries instead: idade
```

!!! info "Both halves together, on purpose"
    The message lists what is **missing** and what came **instead**, because the
    two are almost always one typo. `age` absent and `idade` present is one
    mistake, not two.

## Predicting

```python
from tempestweb.tabular import TabularPredictor

PREDICTOR = TabularPredictor("/models/risk.onnx", manifest="/models/risk.json")


async def score(row: dict[str, float]) -> float:
    """Answer the predicted class's probability."""
    prediction = await PREDICTOR.predict(row)
    return prediction.score
```

The row goes in **any order** — the manifest imposes the one the model needs:

```python
await PREDICTOR.predict({"tenure_months": 18, "age": 30, "income": 3200.0})
```

Several rows in a single run:

```python
predictions = await PREDICTOR.predict_many(rows)
```

!!! note "The model downloads on the first prediction, not before"
    Building a `TabularPredictor` at module scope downloads **nothing**. An app
    that defines three predictors and uses one pays for one.

## The export step: **`zipmap=False` is required**

!!! danger "skl2onnx's default export **does not run in the browser**"
    The default adds a **ZipMap** node, and the `probabilities` output stops
    being a tensor and becomes a `seq(map(int64, float))`. `onnxruntime-web`
    cannot read that:

    ```text
    Can't access output tensor data on index 1.
    ERROR_MESSAGE: Reading data from non-tensor typed value is not supported.
    ```

    This was measured here, with a real export. Pass `zipmap: False`:

    ```python
    onx = to_onnx(model, X[:1], target_opset=15,
                  options={id(model): {"zipmap": False}})
    ```

    If you forget, `native.onnx` raises `unsupported_output` **saying so**,
    rather than repeating the runtime's message — the 539-byte model with ZipMap
    became 389 bytes without it, and started running.

The whole export, in a **throwaway** environment:

```bash
uvx --with scikit-learn --with skl2onnx --with numpy --from onnx python export_model.py
```

```python
import json
from pathlib import Path

import numpy as np
from skl2onnx import to_onnx
from sklearn.linear_model import LogisticRegression

X = np.column_stack([age, income, tenure]).astype(np.float32)
model = LogisticRegression(max_iter=2000).fit(X, y)

onx = to_onnx(model, X[:1], target_opset=15,
              options={id(model): {"zipmap": False}})
Path("risk.onnx").write_bytes(onx.SerializeToString())
Path("risk.json").write_text(json.dumps({
    "version": "2026-08-27",
    "features": ["age", "income", "tenure_months"],
    "outputs": ["label", "probabilities"],
    "classes": ["low", "high"],
}))
```

!!! info "Why `uvx`, and not a dependency"
    `sklearn`, `skl2onnx` and `numpy` are heavy and carry bounds that, in a
    published package, **propagate to every tempestweb consumer** — for a step
    that happens once, on the machine of whoever trains the model. At runtime,
    nothing here depends on them.

## Measured in real Chrome

Same `.onnx`, same `risk.json`, three rows, compared against what **sklearn
answers in Python**:

| Row | sklearn | Chrome → Python | delta |
| --- | --- | --- | --- |
| `income=2000 tenure=6` | `high` p=0.99999702 | `high` p=0.99999708 | 5.96e-08 |
| `income=9000 tenure=90` | `low` p=1.00000000 | `low` p=1.00000000 | 0 |
| `income=2500 tenure=12` | `low` p=0.66673243 | `low` p=0.66673243 | 0 |

Inference over 3 rows: **0.3 ms**. Second load of the same model: **2.7 ms**,
served from the `tw-assets` asset-cache bucket.

!!! info "The cache is the one that already exists"
    The model goes through `client/offline/asset-cache.js` — the same one the
    offline layer uses — so it downloads once per version rather than once per
    session, and concurrent loads of the same URL are deduplicated. A runtime
    without Cache Storage degrades to the plain URL: a cold cache is slower, not
    broken.

## Named errors

| Situation | Error |
| --- | --- |
| Missing (or renamed) feature | `MissingFeatureError`, with what is missing **and** what came instead |
| A feature the model does not know | `UnknownFeatureError` (turn off with `strict=False`) |
| Manifest with no features, or a duplicated one | `ManifestError` |
| A value that is not a number | `ValueError` naming the feature |
| The model answered something unreadable | `PredictionError` |
| Export with ZipMap | `NativeError("unsupported_output")` saying how to re-export |

## Out of scope in this version

- `CompactPredictor` and a configurable execution-provider order — follow-up.
- Training in the browser. This is inference.

## Recap

- The **manifest** is what stops a silently wrong prediction: it declares which
  features the model expects, and **in what order**.
- `predict(row)` takes the row in any order; `predict_many(rows)` runs them all
  in one execution.
- **`zipmap=False` on export is required**, and forgetting it gives an error that
  says so.
- Training and exporting are a build step in a throwaway venv, never a dependency.
- Measured in real Chrome: identical to sklearn to 6e-08.
