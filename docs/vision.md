# Visão computacional (ONNX)

!!! abstract "O que você vai aprender"
    Como rodar **classificação, detecção e segmentação** dentro de um app
    tempestweb — o modelo ONNX roda **no browser** (onnxruntime-web), você recebe
    resultados no estilo Ultralytics e os converte em **schemas JSON** para mandar
    a um backend `tempest-fastapi-sdk`. Ponta a ponta, tudo tipado. 🚀

O módulo `tempestweb.vision` (extra `[vision]`) traz as classes de tarefa
`Classifier` / `Detector` / `Segmenter` com o **mesmo contrato de I/O** do
[`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/) e da camada de visão
do `tempest-fastapi-sdk` — mas rodando sobre o bridge `native.onnx`, então funciona
no browser, onde a wheel `onnxruntime` do Python não existe. ✅

---

## Por que async (e por que no browser)

O `ort-vision-sdk` roda o ONNX Runtime **em processo**. Essa wheel **não existe**
no Pyodide. Então o `tempestweb.vision` mantém todo o **pré e pós-processamento em
Python (NumPy)** — exatamente como o SDK — e cruza **só o `run` do modelo** para o
**onnxruntime-web** através do bridge `native.onnx`.

Esse cruzamento é uma ida-e-volta `postMessage` para o JavaScript, que o browser
**não** roda de forma síncrona. Por isso **construção e predição são `async`**:
você `await`a a criação (o modelo carrega pelo bridge) e `await`a cada `predict`.

!!! info "Mesmo contrato, três lugares"
    `ort-vision-sdk` (Python puro/servidor), `tempest-fastapi-sdk/vision` (backend)
    e `tempestweb.vision` (browser) falam **a mesma** forma de entrada e saída. O
    código de pós-processamento porta sem mudança; só o local do `run` muda.

---

## Instalar

```bash
pip install "tempestweb[vision]"    # ou: uv add "tempestweb[vision]"
```

O extra puxa o [`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/) e o
`numpy`. No Modo A (WASM), coloque o `.onnx` junto do bundle e referencie por um
caminho same-origin (ex.: `"./models/yolov8n.onnx"`).

---

## Detecção — o fluxo completo

Motivação: detectar objetos numa imagem e listar cada caixa. Este é o app inteiro,
runnable nos modos interativos:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb import native
from tempestweb.vision import Detector, to_detection_schemas


@dataclass
class VisionState:
    """Estado da demo de detecção."""

    detector: Detector | None = None
    lines: list[str] = field(default_factory=list)
    status: str = "toque para carregar o modelo"


def make_state() -> VisionState:
    """Estado inicial."""
    return VisionState()


def view(app: App[VisionState]) -> Widget:
    """Botão de carregar + botão de detectar + a lista de detecções."""

    async def load_model() -> None:
        detector = await Detector.create(          # (1)!
            "./models/yolov8n.onnx",
            labels="coco",
        )
        app.set_state(lambda s: setattr(s, "detector", detector))
        app.set_state(lambda s: setattr(s, "status", "modelo pronto"))

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
            s.status = f"{len(lines)} objetos, enfileirados para o backend"

        app.set_state(commit)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=app.state.status, key="status"),
            Button(label="Carregar modelo", on_click=load_model, key="load"),
            Button(label="Detectar", on_click=detect, key="detect"),
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

1.  **Factory async.** `Detector.create(model_url, *, labels=..., providers=...)`
    carrega o `.onnx` pelo bridge e devolve o detector pronto. `**kwargs` extras
    (ex.: `conf_threshold`, `iou_threshold`, `input_size`) vão direto para o
    `ort-vision-sdk`.
2.  **`predict` async** retorna uma lista de 1 elemento (o envelope de resultados);
    pegue o `[0]`.
3.  **Resultados estilo Ultralytics.** Iterar o resultado dá cada detecção com
    `.name`, `.conf` e `.box` (a caixa expõe `.xyxy`). O envelope também tem
    `result.boxes.xyxy` / `.cls` / `.conf` como arrays.
4.  **Para JSON.** `to_detection_schemas(result)` converte para
    `list[DetectionSchema]` (`class_id`, `class_name`, `confidence`, `box`).
5.  **Ponta a ponta.** Aqui enfileiramos cada detecção para o backend com a fila
    offline — veja [Offline + sincronização com backend](offline-sync.md). Poderia
    ser um `native.http.request("POST", ...)` direto.

!!! tip "Labels prontos"
    `labels="coco"` usa o preset COCO de 80 classes embutido no `ort-vision-sdk`.
    Você também pode passar uma lista, um dict `{id: nome}`, um caminho de arquivo,
    ou `None` para gerar `class_N` automaticamente.

---

## Do resultado ao schema JSON

Os resultados do `ort-vision-sdk` são ótimos em Python, mas não são uma resposta
JSON. O `tempestweb.vision` traz três conversores e os schemas Pydantic
correspondentes — que **espelham campo a campo** o `tempest_fastapi_sdk.vision`, de
modo que o cliente tempestweb e um endpoint fastapi-sdk falam **a mesma** forma:

| Conversor | Recebe | Devolve |
|---|---|---|
| `to_detection_schemas(result)` | `DetectionResults` | `list[DetectionSchema]` |
| `to_classification_schema(result)` | `ClassificationResults` | `ClassificationSchema` |
| `to_segmentation_schemas(result)` | `SegmentationResults` | `list[SegmentationSchema]` |

Os schemas:

- **`DetectionSchema`** — `class_id`, `class_name`, `confidence`, `box`
  (`BoundingBoxSchema` com `x1/y1/x2/y2` em pixels).
- **`ClassificationSchema`** — `class_id`, `class_name`, `confidence` (top-1) +
  `probabilities` (lista de `ClassProbabilitySchema` ranqueada).
- **`SegmentationSchema`** — `class_id`, `class_name`, `confidence`, `box` (os
  pixels da máscara são omitidos; só caixa + label por instância).

!!! note "Máscaras não vão no schema"
    `to_segmentation_schemas` devolve **caixa + label** por instância, sem os pixels
    da máscara. Se você precisa da máscara no cliente, leia `result.masks` do
    envelope (estilo Ultralytics) antes de mapear para o schema.

---

## O backend (tempest-fastapi-sdk)

Do outro lado, um endpoint que aceita o **mesmo** schema. Como a forma é idêntica,
o backend valida direto:

```python
from __future__ import annotations

from fastapi import FastAPI
from tempest_fastapi_sdk import register_exception_handlers
from tempestweb.vision import DetectionSchema

app = FastAPI(title="detections-backend")
register_exception_handlers(app)


@app.post("/api/detections", status_code=201)
async def ingest_detection(detection: DetectionSchema) -> dict[str, str]:
    """Recebe uma detecção do cliente tempestweb e a persiste."""
    # ... persista com um BaseRepository, publique num tópico, etc.
    return {"status": "stored", "label": detection.class_name}
```

!!! success "Uma forma, ponta a ponta"
    Inferência no cliente → `to_detection_schemas()` → `POST` → o endpoint valida
    com o **mesmo** shape. Nenhum dos dois pacotes depende do outro — eles só
    concordam no contrato. Para escritas resilientes a rede, enfileire com a
    [fila offline](offline-sync.md) (a idempotência já cuida dos replays).

---

## Classificação e segmentação

A API é idêntica — só muda a classe e o conversor:

=== "Classificação"

    ```python
    from tempestweb.vision import Classifier, to_classification_schema

    clf = await Classifier.create("./models/resnet18.onnx", labels="imagenet")
    result = (await clf.predict("./images/cat.jpg"))[0]
    print(result.name, result.conf)          # top-1 (estilo Ultralytics)
    schema = to_classification_schema(result)  # ClassificationSchema
    ```

=== "Segmentação"

    ```python
    from tempestweb.vision import Segmenter, to_segmentation_schemas

    seg = await Segmenter.create("./models/yolov8n-seg.onnx", labels="coco")
    result = (await seg.predict("./images/street.jpg"))[0]
    for inst in result:
        print(inst.name, inst.conf, inst.box.xyxy)
    schemas = to_segmentation_schemas(result)  # list[SegmentationSchema]
    ```

!!! warning "`run` síncrono não é suportado"
    O bridge `native.onnx` é async: chamar o `run` síncrono do backend levanta
    `RuntimeError`. Sempre use `await task.predict(...)`. As classes de tarefa já
    fazem isso por baixo (via `ort_async_predict`).

---

## Recap

- `pip install "tempestweb[vision]"` traz `Classifier`/`Detector`/`Segmenter`
  (puxa `ort-vision-sdk` + `numpy`).
- O modelo roda **no browser** via `native.onnx` (onnxruntime-web); por isso
  **construir e predizer são `async`**: `await Detector.create(...)` e
  `await det.predict(image)`.
- `predict` devolve os **resultados estilo Ultralytics** do `ort-vision-sdk`
  (`.boxes.xyxy/.cls/.conf`, `.probs`, `.masks`; iteração dá `.name`/`.conf`/`.box`).
- `to_detection_schemas` / `to_classification_schema` / `to_segmentation_schemas`
  convertem para os schemas JSON — que **espelham** o `tempest_fastapi_sdk.vision`,
  fechando o fluxo **inferência no cliente → schema → POST no backend**.
- Envie com [`native.http`](capabilities.md) ou enfileire com a
  [fila offline](offline-sync.md).

Pronto para desenhar as caixas na tela? Os overlays `DetectionOverlay`/
`DetectionBox`/`ResultView` estão em [Componentes prontos](components.md). 🚀
