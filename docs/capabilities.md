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

## Recap

- Capacidades são Web APIs expostas como **awaitables tipados em Python**.
- **Dois backends, uma API:** Modo A chama direto; Modo B proxia por round-trip.
- O envelope é o `native_call`/`native_result` do
  [contrato de fronteira](wire-contract.md).
- Permissões negadas são **fluxo normal**, tratadas como exceção tipada.

A capacidade `storage` se conecta à camada offline — veja
[PWA e offline](pwa.md). 🚀
