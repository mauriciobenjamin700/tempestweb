# Computer vision (ONNX)

!!! abstract "What you'll learn"
    How to run **classification, detection and segmentation** inside a tempestweb
    app — the ONNX model runs **in the browser** (onnxruntime-web), you get
    Ultralytics-style results and convert them into **JSON schemas** to send to a
    `tempest-fastapi-sdk` backend. End to end, fully typed. 🚀

The `tempestweb.vision` module (the `[vision]` extra) ships the task classes
`Classifier` / `Detector` / `Segmenter` with the **same I/O contract** as
[`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/) and
`tempest-fastapi-sdk`'s vision layer — but running over the `native.onnx` bridge,
so it works in the browser, where the Python `onnxruntime` wheel does not exist. ✅

---

## Why async (and why in the browser)

`ort-vision-sdk` runs ONNX Runtime **in-process**. That wheel **does not exist**
under Pyodide. So `tempestweb.vision` keeps all the **pre- and post-processing in
Python (NumPy)** — exactly like the SDK — and crosses **only the model `run`** to
**onnxruntime-web** through the `native.onnx` bridge.

That crossing is a `postMessage` round-trip to JavaScript, which the browser
**cannot** run synchronously. That's why **construction and prediction are
`async`**: you `await` the creation (the model loads over the bridge) and `await`
each `predict`.

!!! info "Same contract, three places"
    `ort-vision-sdk` (pure Python/server), `tempest-fastapi-sdk/vision` (backend)
    and `tempestweb.vision` (browser) speak **the same** input and output shape.
    Post-processing code ports unchanged; only where the `run` happens changes.

---

## Install

```bash
pip install "tempestweb[vision]"    # or: uv add "tempestweb[vision]"
```

The extra pulls [`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/) and
`numpy`. In Mode A (WASM), place the `.onnx` next to the bundle and reference it by
a same-origin path (e.g. `"./models/yolov8n.onnx"`).

---

## Detection — the full flow

Motivation: detect objects in an image and list each box. Here's the whole app,
runnable in the interactive modes:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb import native
from tempestweb.vision import Detector, to_detection_schemas


@dataclass
class VisionState:
    """State for the detection demo."""

    detector: Detector | None = None
    lines: list[str] = field(default_factory=list)
    status: str = "tap to load the model"


def make_state() -> VisionState:
    """Initial state."""
    return VisionState()


def view(app: App[VisionState]) -> Widget:
    """Load button + detect button + the list of detections."""

    async def load_model() -> None:
        detector = await Detector.create(          # (1)!
            "./models/yolov8n.onnx",
            labels="coco",
        )
        app.set_state(lambda s: setattr(s, "detector", detector))
        app.set_state(lambda s: setattr(s, "status", "model ready"))

    async def detect() -> None:
        det = app.state.detector
        if det is None:
            return
        result = (await det.predict("./images/street.jpg"))[0]   # (2)!
        lines = [
            f"{d.name}  {d.conf:.2f}  {tuple(round(v) for v in d.box.xyxy)}"  # (3)!
            for d in result
        ]
        schemas = to_detection_schemas(result)                    # (4)!
        for schema in schemas:
            await native.offline.enqueue(                          # (5)!
                "POST", "/api/detections", schema.model_dump()
            )

        def commit(s: VisionState) -> None:
            s.lines = lines
            s.status = f"{len(lines)} objects, queued for the backend"

        app.set_state(commit)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=app.state.status, key="status"),
            Button(label="Load model", on_click=load_model, key="load"),
            Button(label="Detect", on_click=detect, key="detect"),
            Column(
                style=Style(gap=2.0),
                children=[
                    Text(content=f"• {line}", key=f"det-{i}")
                    for i, line in enumerate(app.state.lines)
                ],
            ),
        ],
    )
```

1.  **Async factory.** `Detector.create(model_url, *, labels=..., providers=...)`
    loads the `.onnx` over the bridge and returns the ready detector. Extra
    `**kwargs` (e.g. `conf_threshold`, `iou_threshold`, `input_size`) are forwarded
    straight to `ort-vision-sdk`.
2.  **Async `predict`** returns a 1-element list (the results envelope); take
    `[0]`.
3.  **Ultralytics-style results.** Iterating the result yields each detection with
    `.name`, `.conf` and `.box` (the box exposes `.xyxy`). The envelope also has
    `result.boxes.xyxy` / `.cls` / `.conf` as arrays.
4.  **To JSON.** `to_detection_schemas(result)` converts to `list[DetectionSchema]`
    (`class_id`, `class_name`, `confidence`, `box`).
5.  **End to end.** Here we queue each detection for the backend with the offline
    queue — see [Offline + backend sync](offline-sync.md). It could be a direct
    `native.http.request("POST", ...)`.

!!! tip "Ready-made labels"
    `labels="coco"` uses the 80-class COCO preset built into `ort-vision-sdk`. You
    can also pass a list, a `{id: name}` dict, a file path, or `None` to
    auto-generate `class_N`.

---

## From result to JSON schema

`ort-vision-sdk`'s results are great in Python, but they're not a JSON response.
`tempestweb.vision` ships three converters and the matching Pydantic schemas —
which **mirror `tempest_fastapi_sdk.vision` field-for-field**, so a tempestweb
client and a fastapi-sdk endpoint speak **the same** shape:

| Converter | Takes | Returns |
|---|---|---|
| `to_detection_schemas(result)` | `DetectionResults` | `list[DetectionSchema]` |
| `to_classification_schema(result)` | `ClassificationResults` | `ClassificationSchema` |
| `to_segmentation_schemas(result)` | `SegmentationResults` | `list[SegmentationSchema]` |

The schemas:

- **`DetectionSchema`** — `class_id`, `class_name`, `confidence`, `box`
  (`BoundingBoxSchema` with `x1/y1/x2/y2` in pixels).
- **`ClassificationSchema`** — `class_id`, `class_name`, `confidence` (top-1) +
  `probabilities` (a ranked list of `ClassProbabilitySchema`).
- **`SegmentationSchema`** — `class_id`, `class_name`, `confidence`, `box` (mask
  pixels are omitted; box + label per instance only).

!!! note "Masks aren't in the schema"
    `to_segmentation_schemas` returns **box + label** per instance, without the
    mask pixels. If you need the mask on the client, read `result.masks` from the
    envelope (Ultralytics-style) before mapping to the schema.

---

## The backend (tempest-fastapi-sdk)

On the far side, an endpoint that accepts the **same** schema. Because the shape is
identical, the backend validates it directly:

```python
from __future__ import annotations

from fastapi import FastAPI
from tempest_fastapi_sdk import register_exception_handlers
from tempestweb.vision import DetectionSchema

app = FastAPI(title="detections-backend")
register_exception_handlers(app)


@app.post("/api/detections", status_code=201)
async def ingest_detection(detection: DetectionSchema) -> dict[str, str]:
    """Receive a detection from the tempestweb client and persist it."""
    # ... persist with a BaseRepository, publish to a topic, etc.
    return {"status": "stored", "label": detection.class_name}
```

!!! success "One shape, end to end"
    Client-side inference → `to_detection_schemas()` → `POST` → the endpoint
    validates with the **same** shape. Neither package depends on the other — they
    only agree on the contract. For network-resilient writes, queue with the
    [offline queue](offline-sync.md) (idempotency already handles replays).

---

## Classification and segmentation

The API is identical — only the class and the converter change:

=== "Classification"

    ```python
    from tempestweb.vision import Classifier, to_classification_schema

    clf = await Classifier.create("./models/resnet18.onnx", labels="imagenet")
    result = (await clf.predict("./images/cat.jpg"))[0]
    print(result.name, result.conf)          # top-1 (Ultralytics-style)
    schema = to_classification_schema(result)  # ClassificationSchema
    ```

=== "Segmentation"

    ```python
    from tempestweb.vision import Segmenter, to_segmentation_schemas

    seg = await Segmenter.create("./models/yolov8n-seg.onnx", labels="coco")
    result = (await seg.predict("./images/street.jpg"))[0]
    for inst in result:
        print(inst.name, inst.conf, inst.box.xyxy)
    schemas = to_segmentation_schemas(result)  # list[SegmentationSchema]
    ```

!!! warning "Synchronous `run` is unsupported"
    The `native.onnx` bridge is async: calling the backend's synchronous `run`
    raises `RuntimeError`. Always use `await task.predict(...)`. The task classes
    already do this under the hood (via `ort_async_predict`).

---

## Recap

- `pip install "tempestweb[vision]"` brings `Classifier`/`Detector`/`Segmenter`
  (pulls `ort-vision-sdk` + `numpy`).
- The model runs **in the browser** via `native.onnx` (onnxruntime-web); that's why
  **constructing and predicting are `async`**: `await Detector.create(...)` and
  `await det.predict(image)`.
- `predict` returns the **Ultralytics-style results** from `ort-vision-sdk`
  (`.boxes.xyxy/.cls/.conf`, `.probs`, `.masks`; iterating yields
  `.name`/`.conf`/`.box`).
- `to_detection_schemas` / `to_classification_schema` / `to_segmentation_schemas`
  convert to the JSON schemas — which **mirror** `tempest_fastapi_sdk.vision`,
  closing the flow **client-side inference → schema → POST to the backend**.
- Send with [`native.http`](capabilities.md) or queue with the
  [offline queue](offline-sync.md).

Ready to draw the boxes on screen? The `DetectionOverlay`/`DetectionBox`/
`ResultView` overlays are in [Ready-made components](components.md). 🚀
