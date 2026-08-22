# Capacidades nativas

As **capacidades** (`native/`) são adaptadores de Web API expostos como
**awaitables tipados em Python**. Você escreve `await geolocation.get()` e recebe
um `Position` tipado — sem tocar em JavaScript. 📡

!!! info "Trilho N — a superfície nativa"
    Esta camada é o **Trilho N** do roadmap (fases N0–N4, detalhadas no
    [plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md)).
    As capacidades funcionam nos **três modos** de execução — cada uma resolve o
    seu backend conforme o `--mode`.

## Uma API Python, três caminhos

O princípio central: **a API Python é sempre a mesma**; o `--mode` escolhe como a
chamada chega na Web API, não o seu código.

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

=== "Modo C — transcrito"

    A chamada `async` é **transcrita para JS** e roda em-processo contra a mesma
    glue de browser — sem Python, sem rede.

    ```python
    pos = await geolocation.get()   # MESMA linha; vira uma chamada JS nativa
    ```

!!! check "O contrato é o mesmo"
    Nos Modos A e B o envelope `native_call`/`native_result` está no
    [contrato de fronteira](wire-contract.md#a-chamada-nativa-modo-b-proxy). No
    Modo C não há envelope — a chamada é transcrita — mas a **assinatura tipada é
    idêntica**. Você escreve uma linha; o modo decide o mecanismo.

!!! info "No Modo B a ponte do cliente já vem ligada"
    Você não precisa escrever nenhuma linha de JavaScript para as capacidades
    funcionarem no Modo B. Ao receber um `native_call`, o transporte
    (`transport-ws.js` · `transport-sse.js`) executa a capacidade pelo mesmo
    registro que o Modo A usa (`dispatch()`, em `native/index.js`) e devolve o
    `native_result` — inclusive o mesmo código de erro. Qualquer shell serve,
    o gerado por `tempestweb build --mode server` inclusive.

    Só se você quiser **interceptar** as chamadas — mockar em teste, exigir uma
    confirmação do usuário, roteá-las para outro lugar — passe `onNativeCall`
    ao criar o transporte; a opção substitui a ponte padrão:

    ```javascript
    const transport = createWebSocketTransport(url, {
      onNativeCall: async (capability, args) => {
        if (capability === "clipboard.write" && !confirm("Copiar?")) {
          throw new Error("cancelled");
        }
        return runMyOwnBridge(capability, args);
      },
    });
    ```

## As capacidades

| Capacidade | API Python | Espelha (React SDK) |
|---|---|---|
| `http` (N0) | `await http.request(...)`, `upload`, `poll`, `idempotency_key` | `createApiClient`/`retry` |
| `audio` (N1) | `await audio.play(src, volume=...)`, `audio.stop()` | `playAudio`/`useAudio` |
| `share` (N2) | `await share(title=..., url=...)` → `ShareResult` | `share`/`isShareSupported` |
| `geolocation` (N3) | `await geolocation.get()` → `Position` | — |
| `clipboard` (N3) | `await clipboard.read()` / `clipboard.write(text)` | — |
| `storage` (N3) | `put`/`get`/`list` (sobre IndexedDB) | `createOfflineStore` |
| `camera` (N4) | `await camera.capture()` → bytes/`Blob` | — |

!!! tip "A superfície completa — Trilho T"
    A tabela acima é o núcleo histórico (Trilho N). O **Trilho T** expandiu a ponte
    para dezenas de grupos — vibração, badge, wake lock, tela cheia, rede,
    sensores, bluetooth, USB, MIDI e muito mais, agrupados por tier (universal /
    muito usado / só-Chromium). O catálogo completo, com um trecho executável por
    grupo, está na [Referência de capacidades nativas](native-reference.md). As
    capacidades de **stream** (consumidas com `async for`) têm um tutorial próprio:
    o [Canal de eventos nativo](native-events.md). 🚀

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
        retry=RetryOptions(attempts=3, base_delay=0.5),
        idempotency_key=key,
    )
    return dict(response.json_body)
```

!!! info "Os botões do `RetryOptions`"
    `attempts` conta a primeira tentativa (`1` desliga o retry), `base_delay`
    é a espera antes do primeiro retry, `factor` multiplica a espera a cada
    falha, `max_delay` limita cada espera e `retry_statuses` diz quais status
    merecem nova tentativa. O modelo **ignora** kwarg que não declara, então um
    nome errado não levanta erro — ele simplesmente não configura nada.

!!! tip "O corpo decodificado é `json_body`"
    `HttpResponse` é um modelo Pydantic com `status`, `ok`, `headers`, `text` e
    `json_body`. O corpo já parseado é o **campo** `json_body` — `response.json()`
    é o serializador do Pydantic (devolve string do modelo inteiro), não o corpo.

!!! tip "Idempotency key evita duplicar efeito"
    Se o retry reentrega a mesma requisição, a `idempotency_key` garante que o
    servidor aplica o efeito **uma só vez**. Essa é a peça que torna a fila offline
    do [Trilho P](pwa.md) segura.

!!! warning "Capacidade lenta dentro do handler trava a sessão"
    A sessão despacha **um evento por vez**. Um `http.request` com
    `RetryOptions(attempts=3, base_delay=0.5)` que bate em timeout gasta segundos —
    e durante todos eles nenhum outro botão daquele usuário responde. O mesmo
    vale para `file.pick` num arquivo grande, upload, e qualquer `onnx.*`.

    Quando a chamada pode demorar, tire-a do handler com
    [`spawn`](../tutorial/best-practices.md#trabalho-longo-o-dispatch-e-serial) e pinte um
    estado de "carregando" antes.

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

### Preview ao vivo e leitor de QR (widgets)

`camera.capture()` é uma **foto**: abre a câmera, pega um frame, fecha. Quando o
app precisa da câmera *ligada* — um preview na tela, um leitor de código —
o widget é o caminho, porque ele mantém o stream enquanto está montado e o fecha
quando sai (câmera aberta é luz acesa no celular de alguém).

```python
from tempest_core import App, Widget
from tempest_core import CameraFrameEvent, QrScanEvent
from tempest_core import CameraPreview, QrScanner


def view(app: App[State]) -> Widget:
    """Show the camera and read codes from it."""

    def framed(event: CameraFrameEvent) -> None:
        # event.data são os bytes do frame em base64; event.width/height, o tamanho.
        app.set_state(lambda state: setattr(state, "last", f"{event.width}x{event.height}"))

    def scanned(event: QrScanEvent) -> None:
        app.set_state(lambda state: setattr(state, "code", event.data))

    return Column(
        key="root",
        children=[
            CameraPreview(
                key="preview",
                facing="back",
                frame_interval_ms=500,
                on_frame=framed,
            ),
            QrScanner(key="scanner", on_scan=scanned),
        ],
    )
```

* **`frame_interval_ms` é o seu orçamento de rede.** No Modo B cada frame é um
  round-trip com a imagem dentro; 500ms é uma escolha, 30fps é um plano de
  saturar a conexão. No Modo A o custo é local, mas ainda é CPU por frame.
* **`facing`** vira o `facingMode` do `getUserMedia`: `back` → `environment`,
  `front` → `user`.
* **Um código lido não é reportado a cada tick.** Ele fica no enquadramento por
  vários frames; o cliente reporta a mudança, não a presença.
* **Contexto seguro obrigatório.** `localhost` conta; um deploy precisa de HTTPS,
  ou o `getUserMedia` não existe.

!!! warning "`QrScanner` depende do `BarcodeDetector` do browser"
    A decodificação é a do próprio navegador — hoje Chrome/Android. Onde ela não
    existe, o widget **mostra a câmera e avisa no console**, sem decodificar: este
    cliente não embute dependência de runtime, então não há decoder de reserva.
    Se você precisa de cobertura ampla, use o `CameraPreview` e decodifique os
    frames você mesmo (é para isso que `on_frame` entrega os bytes).

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

## Instalação do PWA (`native.install`)

Exponha o fluxo de instalação do PWA ao Python: saber se o app é instalável
(`beforeinstallprompt` capturado) ou já instalado, e disparar o prompt após um
gesto real do usuário.

```python
from tempestweb.native import install


async def on_install_tap() -> None:
    """Fire the native install prompt from a button handler."""
    outcome = await install.prompt()   # "accepted" | "dismissed" | "unavailable"


async def maybe_show_install_button() -> bool:
    """Whether to show an Install button."""
    state = await install.state()      # InstallState(can_install, installed)
    return state.can_install and not state.installed
```

`client/native/install.js` envolve o controlador soft de
`client/pwa/install-prompt.js` (suprime o mini-infobar e guarda o evento).

## Extras de build do Modo A (`[wasm]`)

Capacidades que dependem de pacotes Pyodide extras, módulos Python próprios,
assets estáticos ou libs JS declaram-se no `tempestweb.toml`:

```toml
[wasm]
packages = ["numpy", "pillow"]                 # loadPackage além do pydantic do core
modules  = ["famacha", "ort_vision_sdk"]        # pacotes Python bundlados junto do app.py
assets   = ["models/*.onnx", "vendor/ort/*"]    # copiados (path preservado) + precache
scripts  = ["./vendor/ort/ort.wasm.min.js"]     # <script> injetado antes do bootstrap
```

!!! tip "De onde vem cada `module`"
    Cada nome em `modules` é resolvido em duas etapas, nesta ordem:

    1. **Cópia vendida** ao lado do `app.py` (`<projeto>/<module>/`), se existir — o
       comportamento histórico, em que uma cópia versionada no repo vence.
    2. **Pacote instalado** no ambiente (`importlib`) — se não houver cópia vendida,
       o módulo é puxado direto do `site-packages` do seu `.venv`.

    Ou seja: uma dependência que você instala (`uv add ...`) **não precisa ser
    clonada e jogada na raiz do repositório** para ir pro bundle — basta listá-la
    em `modules`. Um nome que não é cópia vendida nem importável falha o build com
    uma mensagem clara.

!!! tip "Nem precisa listar à mão: `tempestweb sync`"
    Para não ter o trabalho de manter `modules` em dia, rode:

    ```bash
    tempestweb sync            # preenche [wasm].modules; --dry-run só mostra
    ```

    Ele lê as `[project.dependencies]` do seu `pyproject.toml`, mantém as que
    estão **instaladas e são puro-Python**, e escreve os nomes de import em
    `[wasm].modules` — preservando o que já estava lá (o pacote do seu app, cópias
    vendidas). Pacotes com código nativo (numpy, pillow) são **pulados** — eles vêm
    do Pyodide via `[wasm].packages` — assim como o próprio framework
    (`tempestweb`, `pydantic`). É idempotente: rodar de novo sem mudar o ambiente
    não escreve nada. Basta ter as dependências no `.venv` e rodar o comando. 🚀

## Recap

- Capacidades são Web APIs expostas como **awaitables tipados em Python**.
- **Uma API, três caminhos:** Modo A chama direto, Modo B proxia por round-trip,
  Modo C transcreve para JS — a assinatura tipada é a mesma.
- Nos Modos A/B o envelope é o `native_call`/`native_result` do
  [contrato de fronteira](wire-contract.md).
- Permissões negadas são **fluxo normal**, tratadas como exceção tipada.

A capacidade `storage` se conecta à camada offline — veja
[PWA e offline](pwa.md). 🚀

!!! info "Referência de API"
    Assinatura de cada capacidade: [`tempestweb.native`](../reference/native.md).
