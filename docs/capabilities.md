# Capacidades nativas

As **capacidades** (`native/`) são adaptadores de Web API expostos como
**awaitables tipados em Python**. Você escreve `await geolocation.get()` e recebe
um `Position` tipado — sem tocar em JavaScript. 📡

!!! info "Em construção (Trilho N)"
    Esta camada é o **Trilho N** do roadmap. As fases N0–N4 estão detalhadas no
    [plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
    Esta página descreve a **superfície planejada** e o modelo de dois backends.

## Dois backends, uma API Python

O princípio central: **cada capacidade tem dois backends, mas a API Python é a
mesma**. O `--mode` escolhe o caminho, não o seu código.

=== "Modo A — direto"

    A chamada vai **direto na Web API** via `pyodide.ffi`, dentro do browser. Sem
    rede.

    ```python
    pos = await geolocation.get()   # chama navigator.geolocation no browser
    ```

=== "Modo B — proxy"

    A chamada é **proxiada por um round-trip**: o servidor emite um pedido nativo
    pelo transporte (WS/SSE), o cliente executa a Web API e devolve o resultado
    tipado.

    ```python
    pos = await geolocation.get()   # MESMA linha; dispara native_call/native_result
    ```

!!! check "O contrato é o mesmo"
    O envelope `native_call`/`native_result` está no
    [contrato de fronteira](wire-contract.md#a-chamada-nativa-modo-b-proxy). Só o
    transporte difere — a assinatura tipada mora no contrato, não no transporte.

## As capacidades planejadas

| Capacidade | API Python | Espelha (React SDK) |
|---|---|---|
| `http` (N0) | `await http.request(...)`, `upload`, `poll`, `idempotency_key` | `createApiClient`/`retry` |
| `audio` (N1) | `await audio.play(src, volume=...)`, `audio.stop()` | `playAudio`/`useAudio` |
| `share` (N2) | `await share(title=..., url=...)` → `ShareResult` | `share`/`isShareSupported` |
| `geolocation` (N3) | `await geolocation.get()` → `Position` | — |
| `clipboard` (N3) | `await clipboard.read()` / `clipboard.write(text)` | — |
| `storage` (N3) | `put`/`get`/`list` (sobre IndexedDB) | `createOfflineStore` |
| `camera` (N4) | `await camera.capture()` → bytes/`Blob` | — |

## Exemplo: HTTP tipado com retry

O `native.http` (N0) é a base do replay offline. Uma requisição com retry e
idempotency key:

```python
from tempestweb.native import http
from tempestweb.native.http import RetryOptions


async def submit_order(payload: dict[str, object]) -> dict[str, object]:
    """Submit an order with retry and an idempotency key.

    Args:
        payload: The order body to POST.

    Returns:
        The decoded JSON response.
    """
    key = http.generate_idempotency_key()
    response = await http.request(
        "POST",
        "/api/orders",
        json=payload,
        retry=RetryOptions(attempts=3, backoff=0.5),
        idempotency_key=key,
    )
    return response.json()
```

!!! tip "Idempotency key evita duplicar efeito"
    Se o retry reentrega a mesma requisição, a `idempotency_key` garante que o
    servidor aplica o efeito **uma só vez**. Essa é a peça que torna a fila offline
    do [Trilho P](pwa.md) segura.

## Exemplo: geolocalização

```python
from tempestweb.native import geolocation


async def center_map(app: object) -> None:
    """Read the device position and update the app state.

    Args:
        app: The running app handle.
    """
    pos = await geolocation.get()   # Position(lat=..., lon=...)
    app.set_state(lambda s: setattr(s, "center", (pos.lat, pos.lon)))
```

!!! warning "Permissão é caminho normal, não exceção fatal"
    Geolocation, clipboard e camera exigem **permissão** e **contexto seguro**
    (HTTPS). Trate a negação como um fluxo normal — uma exceção tipada que sua UI
    apresenta com elegância, não um crash.

## Câmera no Modo B (sempre no cliente)

A captura de câmera **sempre acontece no cliente**, mesmo no Modo B. Quando você
chama `await camera.capture()` "no servidor", o round-trip dispara a captura no
browser e a foto volta tipada (base64 ou referência de blob).

```python
from tempestweb.native import camera


async def take_photo() -> bytes:
    """Capture a photo from the device camera.

    Returns:
        The captured image bytes.
    """
    blob = await camera.capture()   # captura no cliente; volta tipado no Modo B
    return blob.data
```

!!! note "Comprima antes de subir"
    No Modo B a foto atravessa a rede no round-trip. Comprima no cliente antes de
    devolver para manter o payload pequeno.

## Inferência ONNX no browser (`native.onnx`)

`onnxruntime` (a extensão C do CPython) **não tem wheel Pyodide** — Python no
browser não roda um grafo ONNX em-processo. A capacidade `onnx` cobre o vão:
o grafo roda em JavaScript via **onnxruntime-web** (build WASM), dirigido pela
mesma costura `native_call`. Você faz o pré/pós-processamento em Python (numpy +
pillow, ambos no Pyodide) e atravessa só a execução do tensor.

```python
from tempestweb.native import onnx
from tempestweb.native.onnx import Tensor


async def detect(input_b64: str) -> dict[str, Tensor]:
    """Run a YOLO ONNX model loaded same-origin from the artifact."""
    model = await onnx.load("./models/detect.onnx")       # compila a sessão (cache no JS)
    feeds = {model.input_name: Tensor(data_base64=input_b64, dims=[1, 3, 640, 640])}
    return await onnx.run(model.session_id, feeds)         # → {nome: Tensor}
```

Carregue o `onnxruntime-web` por `[wasm].scripts` e vendore-o (e os `.onnx`) por
`[wasm].assets`, para o service worker precachear tudo e a inferência rodar
**offline**. O provedor `wasm` é forçado (o build web não tem alguns kernels sob
WebGPU). Tensores cruzam como bytes base64 + shape + dtype — a capacidade é
numpy-free; o lado Python (que tem numpy) serializa.

## Salvar arquivo gerado (`native.file`)

O browser não tem escrita síncrona de arquivo. `file.save` entrega um blob gerado
em Python por `navigator.share({files})` (quando a plataforma aceita) ou por
download via `<a download>` (desktop), reportando qual caminho rodou.

```python
from tempestweb.native import file


async def export_zip(zip_bytes: bytes) -> None:
    """Share or download a generated ZIP."""
    await file.save("historico.zip", zip_bytes, mime_type="application/zip")
```

## Extras de build do Modo A (`[wasm]`)

Capacidades que dependem de pacotes Pyodide extras, módulos Python próprios,
assets estáticos ou libs JS declaram-se no `tempestweb.toml`:

```toml
[wasm]
packages = ["numpy", "pillow"]                 # loadPackage além do pydantic do core
modules  = ["famacha"]                          # pacotes Python bundlados junto do app.py
assets   = ["models/*.onnx", "vendor/ort/*"]    # copiados (path preservado) + precache
scripts  = ["./vendor/ort/ort.wasm.min.js"]     # <script> injetado antes do bootstrap
```

## Recap

- Capacidades são Web APIs expostas como **awaitables tipados em Python**.
- **Dois backends, uma API:** Modo A chama direto; Modo B proxia por round-trip.
- O envelope é o `native_call`/`native_result` do
  [contrato de fronteira](wire-contract.md).
- Permissões negadas são **fluxo normal**, tratadas como exceção tipada.

A capacidade `storage` se conecta à camada offline — veja
[PWA e offline](pwa.md). 🚀
