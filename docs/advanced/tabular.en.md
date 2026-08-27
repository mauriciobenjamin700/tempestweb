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

## What weighs is not the model — it is the runtime

!!! danger "A 660-byte model, a 14 MB runtime"
    The `.onnx` of a 30-feature `LogisticRegression` is **660 bytes**. The
    `onnxruntime-web` build that runs it is **13.96 MB** (3.58 MB gzipped) in its
    leanest bundle. The runtime is **21,000×** the model — and it, not the model,
    decides whether tabular inference fits in your artifact.

Measured exports (`skl2onnx` with `zipmap=False`, `scikit-learn` over
`load_breast_cancer` and `make_classification`):

| Model | Features | `.onnx` | gzip |
| --- | --- | --- | --- |
| `LogisticRegression` | 30 | 660 B | 539 B |
| `DecisionTreeClassifier(max_depth=8)` | 30 | 2,167 B | 812 B |
| `GradientBoostingClassifier(n=100)` | 30 | 54,217 B | 7,700 B |
| `RandomForestClassifier(n=100, d=8)` | 30 | 154,013 B | 20,192 B |
| `LogisticRegression`, 3 classes | 120 | 2,259 B | 1,915 B |
| `RandomForestClassifier(n=300, d=12)` | 120 | **14,292,489 B** | 1,623,887 B |

On the runtime side, `onnxruntime-web` 1.29.0, measured by what Chrome
**actually downloads**:

| Bundle loaded via `[wasm].scripts` | JS | WebAssembly | gzip total |
| --- | --- | --- | --- |
| `ort.wasm.min.js` (CPU only) | 50,196 B | `ort-wasm-simd-threaded.wasm` — 13,961,845 B | **3.58 MB** |
| `ort.min.js` (package default) | 368,008 B | `…-threaded.jsep.wasm` — 27,797,172 B | **6.48 MB** |
| `ort.all.min.js` | 819,591 B | `…-threaded.jsep.wasm` — 27,797,172 B | **6.64 MB** |

!!! tip "Load `ort.wasm.min.js`, not `ort.min.js`"
    The 1.29.0 default bundle pulls the **jsep** WebAssembly (WebGPU + WebNN)
    even when the session asks for `executionProviders: ["wasm"]` only — measured
    here, from the network panel. Switching to `ort.wasm.min.js` saves
    **13.8 MB raw / 2.9 MB gzipped** without touching a line of Python. It is
    what [`[wasm].scripts` in the capabilities guide](capabilities.en.md#mode-a-build-extras-wasm)
    already recommends.

For scale, the tutorial's own `counter` built in both modes, with no ML at all:

| Artifact | raw | gzip |
| --- | --- | --- |
| Mode A `--offline` (vendored Pyodide + stdlib + pydantic) | 15.6 MB | 8.4 MB |
| Mode C (transpile) | 1.98 MB | 291 KB |

So: `ort.wasm.min.js` is **+43% gzipped** on an offline Mode A artifact, and
**12× the whole Mode C artifact**.

### Provider: the `["wasm"]` default, with the number behind it

Inference measured in real Chrome (`onnxruntime-web` 1.29.0, 50 runs, median and
p95, session already compiled):

| Model | Rows per run | median | p95 |
| --- | --- | --- | --- |
| `LogisticRegression` 30f | 3 | **0.1 ms** | 0.3 ms |
| `LogisticRegression` 30f | 1,000 | 0.1 ms | 0.3 ms |
| `RandomForest` 100×d8 | 3 | 0.1 ms | 0.1 ms |
| `RandomForest` 100×d8 | 1,000 | 3.4 ms | 3.7 ms |

Creating the session costs 225 ms the first time (the WASM runtime booting with
it) and 2.1–8.3 ms afterwards.

!!! info "WebGPU was not measured here — and the default does not hinge on it"
    This measurement's environment (WSL2, headless Chrome) exposes
    `navigator.gpu` but `requestAdapter()` returns `null`, and `onnxruntime-web`
    refuses with `no available backend found. ERR: [webgpu] Failed to get GPU
    adapter` — even with `--enable-unsafe-swiftshader`. What keeps
    `DEFAULT_PROVIDERS = ["wasm"]` is the other side of the ledger: the WebGPU EP
    **requires the jsep runtime**, 2.9 MB gzipped more, to speed up an inference
    that already takes **0.1 ms**. A 100% win there saves 0.1 ms and is paid for
    in megabytes.

    `providers=` still takes whatever order you want — an app that runs vision
    and tabular on the same page has already downloaded jsep and can experiment
    at no new cost.

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

- `CompactPredictor` — a compact format that runs with no inference runtime at
  all. The measurement above is the case for it, tracked in
  [issue #191](https://github.com/mauriciobenjamin700/tempestweb/issues/191):
  what weighs is `onnxruntime-web`, not the `.onnx`.
- Execution-provider order **is already configurable** via `providers=`; what
  the measurement settled is the default, `["wasm"]`.
- Training in the browser. This is inference.

## Recap

- The **manifest** is what stops a silently wrong prediction: it declares which
  features the model expects, and **in what order**.
- `predict(row)` takes the row in any order; `predict_many(rows)` runs them all
  in one execution.
- **`zipmap=False` on export is required**, and forgetting it gives an error that
  says so.
- Training and exporting are a build step in a throwaway venv, never a dependency.
- Measured in real Chrome: identical to sklearn down to 6e-08, and **0.1 ms**
  per 3-row inference.
- **The runtime is what weighs**: 13.96 MB of `onnxruntime-web` for a 660-byte
  model. Load `ort.wasm.min.js` and save 13.8 MB raw.
