# Captura de Foto com a Câmera 📸

Construa um app que acessa a câmera do dispositivo, exibe um spinner durante a captura e mostra uma prévia da foto com metadados — tudo escrito em Python puro.

---

## O que você vai construir

Um app de captura de câmera com ciclo de vida completo:

- 🟢 **Estado IDLE** — botão "Capture" visível, pronto para disparar
- ⏳ **Estado CAPTURING** — spinner + mensagem "Accessing camera…" enquanto o browser captura o frame
- 🖼 **Estado CAPTURED** — prévia da foto em `data:` URI dentro de um `Card`, com badges de formato, largura e altura
- ❌ **Estado ERROR** — mensagem de erro amigável quando o usuário nega a permissão de câmera, com botão "Try again"

!!! note "Nota — capabilidade nativa N4"
    A câmera é sempre acessada **no browser**, nunca no servidor. No Modo A (WASM) o Python chama `navigator.mediaDevices` via FFI; no Modo B (servidor) o Python envia um `native_call` pelo WebSocket e o cliente JS executa a mesma chamada, devolvendo a foto como `native_result`. A sua função `view` não muda em nenhum dos modos.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada (opcional):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor
- [Capacidades nativas](../capabilities.md) — o modelo de bridge

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/photo-capture
touch examples/photo-capture/app.py
```

---

## Passo 1 — Entendendo o ciclo de vida

Antes de escrever código, pense nos **quatro estados** possíveis da UI:

| Fase | O que o usuário vê |
|---|---|
| `IDLE` | Título + subtítulo + botão "Capture" |
| `CAPTURING` | Título + spinner + texto "Accessing camera…" |
| `CAPTURED` | Título + card com foto + badges de metadados + botões "Capture" e "Clear" |
| `ERROR` | Título + card de erro + botão "Try again" |

Esse diagrama resume as transições:

```
IDLE ──(clique Capture)──► CAPTURING
                               │
              ┌────────────────┴────────────────┐
              ▼ (foto retornada)                 ▼ (NativeError)
           CAPTURED                            ERROR
              │                                  │
       (clique Clear)                    (clique Try again)
              │                                  │
              └──────────────► IDLE ◄────────────┘
```

---

## Passo 2 — A enumeração de fases

Use `StrEnum` para que as fases sejam legíveis em logs e no wire format:

```python
from enum import StrEnum


class Phase(StrEnum):
    """Lifecycle phase of the camera capture flow.

    Attributes:
        IDLE: Nothing has been captured yet — the *Capture* button is shown.
        CAPTURING: A capture is in flight — the spinner is shown.
        CAPTURED: A photo was returned — the preview card is shown.
        ERROR: The capture failed — a brief error message is shown.
    """

    IDLE = "idle"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    ERROR = "error"
```

!!! tip "Dica — `StrEnum` vs `str`"
    `Phase.IDLE == "idle"` avalia como `True`, então você pode comparar com `is` (identidade de enum) **ou** com `==` (valor string). O app usa `is` para ser explícito.

---

## Passo 3 — O tipo `Photo` e o alias `Capturer`

`tempestweb.native.camera.Photo` é um modelo Pydantic **frozen** (imutável) que o bridge devolve após a captura:

```python
from tempestweb.native.camera import Photo
```

| Campo | Tipo | Descrição |
|---|---|---|
| `mime_type` | `str` | Ex.: `"image/jpeg"`, `"image/png"` |
| `width` | `int` | Largura em pixels |
| `height` | `int` | Altura em pixels |
| `data_base64` | `str` | Bytes da imagem codificados em base64 |

`photo.to_bytes()` decodifica `data_base64` para `bytes` — útil para fazer upload via `native.http`.

O alias `Capturer` nomeia o tipo do callable injetado no estado:

```python
from collections.abc import Awaitable, Callable

Capturer = Callable[[], Awaitable[Photo]]
```

---

## Passo 4 — Estado e a captura padrão

```python
from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb.native import NativeError
from tempestweb.native import camera as _camera
from tempestweb.native.camera import Photo

Capturer = Callable[[], Awaitable[Photo]]


async def _default_capture() -> Photo:
    """Capture a rear-facing JPEG at 85 % quality.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the user denies permission, no camera is available, or
            the page is not in a secure context.
        BrowserUnavailableError: If no native bridge is installed.
    """
    return await _camera.capture(facing="environment", quality=0.85)


@dataclass
class PhotoState:
    """State for the camera-capture app.

    Attributes:
        phase: The current lifecycle phase.
        photo: The most-recently captured photo, or ``None`` before the first
            successful capture.
        error: The error message surfaced when ``phase`` is ``ERROR``.
        capture: The injected coroutine factory that performs the capture;
            defaults to ``native.camera.capture`` so the app works
            out-of-the-box in both modes.
    """

    phase: Phase = Phase.IDLE
    photo: Photo | None = None
    error: str = ""
    capture: Capturer = field(default=_default_capture)


def make_state() -> PhotoState:
    """Build the initial, idle camera-capture state.

    Returns:
        A fresh :class:`PhotoState` in the ``IDLE`` phase.
    """
    return PhotoState()
```

!!! info "Por que `capture` fica no estado?"
    Injetar o callable de captura diretamente em `PhotoState` é o padrão de **dependency injection** do tempestweb: em produção, o campo usa `_default_capture` (que chama a câmera real); nos testes, você passa um callable falso — sem monkey-patching, sem mock global, sem bridge real necessária. Veja a seção de [testes](#testando-sem-camera) mais adiante.

---

## Passo 5 — O helper `_data_uri`

Para exibir a foto como `<img>`, precisamos de uma URI `data:`:

```python
import base64


def _data_uri(photo: Photo) -> str:
    """Build a browser-safe ``data:`` URI from a :class:`Photo`.

    Args:
        photo: The captured photo with base64-encoded bytes.

    Returns:
        A ``data:<mime_type>;base64,<data_base64>`` string suitable for use as
        an ``<img src>`` attribute.
    """
    try:
        base64.b64decode(photo.data_base64, validate=True)
    except Exception:
        return ""
    return f"data:{photo.mime_type};base64,{photo.data_base64}"
```

!!! tip "Dica — validação defensiva"
    Antes de montar a URI, `b64decode(..., validate=True)` verifica se o payload é base64 válido. Se o bridge ou um teste enviar bytes corrompidos, `_data_uri` retorna `""` em vez de produzir uma URI quebrada no DOM. A `view` trata isso mostrando um placeholder de texto.

---

## Passo 6 — Os handlers assíncronos

Os handlers vivem **dentro de `view()`**, capturando `app` por closure. Isso é intencional — cada render cria closures frescas ligadas ao estado atual.

### Handler `do_capture` (assíncrono)

```python
async def do_capture() -> None:
    """Drive the async capture flow through all lifecycle phases."""
    app.set_state(lambda s: setattr(s, "phase", Phase.CAPTURING))
    try:
        photo: Photo = await app.state.capture()
    except NativeError as exc:
        msg = str(exc)

        def _on_native_error(s: PhotoState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_native_error)
        return
    except Exception as exc:
        message = str(exc)

        def _on_error(s: PhotoState) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(_on_error)
        return

    def _on_success(s: PhotoState) -> None:
        s.phase = Phase.CAPTURED
        s.photo = photo

    app.set_state(_on_success)
```

Observe as **três transições de estado** explícitas:

1. `IDLE → CAPTURING` — imediatamente ao entrar no handler.
2. `CAPTURING → ERROR` — se `NativeError` (permissão negada, câmera indisponível) ou qualquer outra exceção.
3. `CAPTURING → CAPTURED` — após a foto ser retornada com sucesso.

!!! warning "Capturando `NativeError` separadamente"
    `NativeError` carrega um `code` legível por máquina (`"permission_denied"`, `"unavailable"`, `"insecure_context"`). Capturá-lo **antes** de `Exception` garante que você possa, futuramente, apresentar mensagens específicas por código sem alterar a estrutura do handler.

### Handler `reset` (síncrono)

```python
def reset() -> None:
    """Reset the state back to the idle phase so the user can capture again."""

    def _do_reset(s: PhotoState) -> None:
        s.phase = Phase.IDLE
        s.photo = None
        s.error = ""

    app.set_state(_do_reset)
```

---

## Passo 7 — Construindo a árvore de widgets por fase

A função `view` é uma transformação **pura e sem I/O** de `PhotoState` → árvore de widgets. Toda a lógica de branch fica num `if/elif/else` sobre `app.state.phase`.

### Fase IDLE

```python
header = Text(
    content="Camera Capture",
    style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
    key="title",
)
subtitle = Text(
    content="Tap the button below to capture a photo from your device camera.",
    style=Style(font_size=14.0),
    key="subtitle",
)
capture_btn = Button(label="Capture", on_click=do_capture, key="capture")

if app.state.phase is Phase.IDLE:
    body_children = [header, subtitle, capture_btn]
```

### Fase CAPTURING

```python
elif app.state.phase is Phase.CAPTURING:
    body_children = [
        header,
        Spinner(key="spinner"),
        Text(content="Accessing camera…", style=Style(font_size=14.0), key="wait"),
    ]
```

!!! note "`Spinner` — feedback visual imediato"
    `Spinner` não precisa de parâmetros além do `key`. O reconciliador troca o botão pelo spinner em um único patch — o usuário vê a transição instantaneamente.

### Fase ERROR

```python
elif app.state.phase is Phase.ERROR:
    body_children = [
        header,
        Card(
            key="error-card",
            children=[
                Text(
                    content="Camera unavailable",
                    style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
                    key="err-title",
                ),
                Text(
                    content=app.state.error,
                    style=Style(font_size=13.0),
                    key="err-msg",
                ),
            ],
        ),
        Button(label="Try again", on_click=do_capture, key="retry"),
    ]
```

### Fase CAPTURED

Esta é a fase mais rica: prévia da foto + badges de metadados.

```python
else:  # CAPTURED
    photo = app.state.photo
    assert photo is not None, "phase is CAPTURED but photo is None"

    data_uri = _data_uri(photo)
    image_widget: Widget
    if data_uri:
        image_widget = Image(
            src=data_uri,
            fit=ImageFit.COVER,
            alt="Captured photo",
            key="preview-img",
            style=Style(width=320.0, height=240.0, radius=8.0),
        )
    else:
        image_widget = Text(
            content="(image preview unavailable)",
            style=Style(font_size=12.0),
            key="preview-placeholder",
        )

    meta_row: list[Widget] = [
        _meta_badge("Format", photo.mime_type, "badge-mime"),
        _meta_badge("Width", f"{photo.width} px", "badge-width"),
        _meta_badge("Height", f"{photo.height} px", "badge-height"),
    ]

    body_children = [
        header,
        Card(
            key="photo-card",
            children=[
                image_widget,
                Divider(key="divider"),
                Row(
                    style=Style(
                        gap=8.0,
                        justify=JustifyContent.START,
                        align=AlignItems.CENTER,
                    ),
                    children=meta_row,
                    key="meta-row",
                ),
            ],
        ),
        Row(
            style=Style(gap=8.0, justify=JustifyContent.CENTER),
            children=[
                capture_btn,
                Button(label="Clear", on_click=reset, key="clear"),
            ],
            key="actions",
        ),
    ]
```

### Raiz da árvore

```python
return Column(
    style=Style(gap=16.0, padding=Edge.all(20.0)),
    children=body_children,
)
```

---

## Passo 8 — O helper `_meta_badge`

Cada badge de metadado é um `Card` pequeno com dois `Text` empilhados:

```python
def _meta_badge(label: str, value: str, key: str) -> Widget:
    """Build a small metadata badge widget.

    Args:
        label: The badge label (e.g. ``"Format"``).
        value: The badge value (e.g. ``"image/jpeg"``).
        key: The widget key for reconciliation.

    Returns:
        A :class:`~tempestweb._core.components.Card` containing a label/value
        column.
    """
    return Card(
        key=key,
        style=Style(padding=Edge.symmetric(vertical=6.0, horizontal=10.0)),
        children=[
            Text(
                content=label,
                style=Style(font_size=10.0, font_weight=FontWeight.BOLD),
                key=f"{key}-label",
            ),
            Text(
                content=value,
                style=Style(font_size=12.0),
                key=f"{key}-value",
            ),
        ],
    )
```

---

## O app completo

Aqui está o arquivo `examples/photo-capture/app.py` completo, pronto para copiar:

```python
"""Camera capture view — exercises ``native.camera.capture()`` (N4).

Like :mod:`examples.fetch.app`, this exact ``view`` runs unchanged in both
modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

It demonstrates an async native-capability handler: pressing *Capture* runs an
``async`` handler that:

1. Flips the view into a ``CAPTURING`` loading state (showing a
   :class:`~tempestweb._core.widgets.Spinner`).
2. Awaits the injected ``capture`` callable (defaults to
   ``native.camera.capture``), which resolves to a :class:`~tempestweb.native.Photo`
   carrying the MIME type, pixel dimensions, and base64-encoded bytes.
3. Renders the result in a :class:`~tempestweb._core.components.Card` with a
   data-URI :class:`~tempestweb._core.widgets.Image` preview and metadata row.

If the user denies camera permission, the bridge raises a
:class:`~tempestweb.native.NativeError` — the handler catches it and surfaces a
tidy error message rather than crashing the view.

The ``capture`` callable is **dependency-injected** into :class:`PhotoState`, so
the view is fully deterministic under test (no real bridge needed; a fake bridge
can also be installed for integration tests). The initial render never calls the
capability.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card, Divider
from tempestweb._core.style import AlignItems, Edge, FontWeight, JustifyContent
from tempestweb._core.widgets import Button, Column, Image, ImageFit, Row, Spinner, Text
from tempestweb.native import NativeError
from tempestweb.native import camera as _camera
from tempestweb.native.camera import Photo

# ---------------------------------------------------------------------------
# Type alias for the injected capture callable.
# ---------------------------------------------------------------------------

#: A coroutine factory that captures a single photo.  Injected into state so
#: the example stays deterministic under test; in a real app the default is
#: ``native.camera.capture``.
Capturer = Callable[[], Awaitable[Photo]]


# ---------------------------------------------------------------------------
# Phase enumeration
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phase of the camera capture flow.

    Attributes:
        IDLE: Nothing has been captured yet — the *Capture* button is shown.
        CAPTURING: A capture is in flight — the spinner is shown.
        CAPTURED: A photo was returned — the preview card is shown.
        ERROR: The capture failed — a brief error message is shown.
    """

    IDLE = "idle"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Default capture callable (wraps the real native capability)
# ---------------------------------------------------------------------------


async def _default_capture() -> Photo:
    """Capture a rear-facing JPEG at 85 % quality.

    This is the production default injected into :class:`PhotoState`. It is
    never called during testing (the fake bridge or a mock callable is
    injected instead), but it **is** called in live deployments — the
    docstring preserves the intent for readers.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the user denies permission, no camera is available, or
            the page is not in a secure context.
        BrowserUnavailableError: If no native bridge is installed (Mode A
            requires the FFI bridge; Mode B requires the proxy bridge).
    """
    return await _camera.capture(facing="environment", quality=0.85)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class PhotoState:
    """State for the camera-capture app.

    Attributes:
        phase: The current lifecycle phase.
        photo: The most-recently captured photo, or ``None`` before the first
            successful capture.
        error: The error message surfaced when ``phase`` is ``ERROR``.
        capture: The injected coroutine factory that performs the capture;
            defaults to ``native.camera.capture`` so the app works
            out-of-the-box in both modes.
    """

    phase: Phase = Phase.IDLE
    photo: Photo | None = None
    error: str = ""
    capture: Capturer = field(default=_default_capture)


def make_state() -> PhotoState:
    """Build the initial, idle camera-capture state.

    Returns:
        A fresh :class:`PhotoState` in the ``IDLE`` phase.
    """
    return PhotoState()


# ---------------------------------------------------------------------------
# Helper: build a data URI from a Photo
# ---------------------------------------------------------------------------


def _data_uri(photo: Photo) -> str:
    """Build a browser-safe ``data:`` URI from a :class:`Photo`.

    Args:
        photo: The captured photo with base64-encoded bytes.

    Returns:
        A ``data:<mime_type>;base64,<data_base64>`` string suitable for use as
        an ``<img src>`` attribute.
    """
    try:
        base64.b64decode(photo.data_base64, validate=True)
    except Exception:
        return ""
    return f"data:{photo.mime_type};base64,{photo.data_base64}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[PhotoState]) -> Widget:
    """Render the camera-capture UI from the current lifecycle phase.

    The view is a thin, stateless transformation of :class:`PhotoState` to a
    widget tree.  All state mutations happen inside the ``do_capture`` async
    handler — the view function itself never performs I/O.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state phase.
    """

    # ------------------------------------------------------------------
    # Async handler — IDLE → CAPTURING → CAPTURED | ERROR
    # ------------------------------------------------------------------

    async def do_capture() -> None:
        """Drive the async capture flow through all lifecycle phases."""
        app.set_state(lambda s: setattr(s, "phase", Phase.CAPTURING))
        try:
            photo: Photo = await app.state.capture()
        except NativeError as exc:
            msg = str(exc)

            def _on_native_error(s: PhotoState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_native_error)
            return
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            message = str(exc)

            def _on_error(s: PhotoState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(_on_error)
            return

        def _on_success(s: PhotoState) -> None:
            s.phase = Phase.CAPTURED
            s.photo = photo

        app.set_state(_on_success)

    # ------------------------------------------------------------------
    # Reset handler — go back to IDLE
    # ------------------------------------------------------------------

    def reset() -> None:
        """Reset the state back to the idle phase so the user can capture again."""

        def _do_reset(s: PhotoState) -> None:
            s.phase = Phase.IDLE
            s.photo = None
            s.error = ""

        app.set_state(_do_reset)

    # ------------------------------------------------------------------
    # Body widgets — vary by phase
    # ------------------------------------------------------------------

    header = Text(
        content="Camera Capture",
        style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        key="title",
    )
    subtitle = Text(
        content="Tap the button below to capture a photo from your device camera.",
        style=Style(font_size=14.0),
        key="subtitle",
    )
    capture_btn = Button(label="Capture", on_click=do_capture, key="capture")

    body_children: list[Widget]

    if app.state.phase is Phase.IDLE:
        body_children = [
            header,
            subtitle,
            capture_btn,
        ]

    elif app.state.phase is Phase.CAPTURING:
        body_children = [
            header,
            Spinner(key="spinner"),
            Text(content="Accessing camera…", style=Style(font_size=14.0), key="wait"),
        ]

    elif app.state.phase is Phase.ERROR:
        body_children = [
            header,
            Card(
                key="error-card",
                children=[
                    Text(
                        content="Camera unavailable",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                        key="err-title",
                    ),
                    Text(
                        content=app.state.error,
                        style=Style(font_size=13.0),
                        key="err-msg",
                    ),
                ],
            ),
            Button(label="Try again", on_click=do_capture, key="retry"),
        ]

    else:  # CAPTURED
        photo = app.state.photo
        assert photo is not None, "phase is CAPTURED but photo is None"

        data_uri = _data_uri(photo)
        image_widget: Widget
        if data_uri:
            image_widget = Image(
                src=data_uri,
                fit=ImageFit.COVER,
                alt="Captured photo",
                key="preview-img",
                style=Style(width=320.0, height=240.0, radius=8.0),
            )
        else:
            image_widget = Text(
                content="(image preview unavailable)",
                style=Style(font_size=12.0),
                key="preview-placeholder",
            )

        meta_row: list[Widget] = [
            _meta_badge("Format", photo.mime_type, "badge-mime"),
            _meta_badge("Width", f"{photo.width} px", "badge-width"),
            _meta_badge("Height", f"{photo.height} px", "badge-height"),
        ]

        body_children = [
            header,
            Card(
                key="photo-card",
                children=[
                    image_widget,
                    Divider(key="divider"),
                    Row(
                        style=Style(
                            gap=8.0,
                            justify=JustifyContent.START,
                            align=AlignItems.CENTER,
                        ),
                        children=meta_row,
                        key="meta-row",
                    ),
                ],
            ),
            Row(
                style=Style(gap=8.0, justify=JustifyContent.CENTER),
                children=[
                    capture_btn,
                    Button(label="Clear", on_click=reset, key="clear"),
                ],
                key="actions",
            ),
        ]

    return Column(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=body_children,
    )


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _meta_badge(label: str, value: str, key: str) -> Widget:
    """Build a small metadata badge widget.

    Args:
        label: The badge label (e.g. ``"Format"``).
        value: The badge value (e.g. ``"image/jpeg"``).
        key: The widget key for reconciliation.

    Returns:
        A :class:`~tempestweb._core.components.Card` containing a label/value
        column.
    """
    return Card(
        key=key,
        style=Style(padding=Edge.symmetric(vertical=6.0, horizontal=10.0)),
        children=[
            Text(
                content=label,
                style=Style(font_size=10.0, font_weight=FontWeight.BOLD),
                key=f"{key}-label",
            ),
            Text(
                content=value,
                style=Style(font_size=12.0),
                key=f"{key}-value",
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

!!! warning "Capacidades nativas precisam de um bridge"
    `native.camera.capture` precisa de um **bridge** instalado para funcionar. Sem bridge, qualquer chamada à capability levanta `BrowserUnavailableError` imediatamente.

    - **Modo A (WASM):** o runtime instala um `FFIBridge` automaticamente ao carregar o Pyodide no browser. Você não precisa fazer nada além de rodar o servidor de dev.
    - **Modo B (servidor):** cada sessão de WebSocket cria e instala um `ProxyBridge` automaticamente. O servidor envia um `native_call` ao cliente; o cliente JS executa `navigator.mediaDevices.getUserMedia`, captura o frame e devolve via `native_result`.
    - **Fora do browser** (script Python puro, servidor sem sessão ativa): não há bridge → qualquer chamada à capability falha com `BrowserUnavailableError`. É o comportamento correto — use um fake em testes (veja abaixo).

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/photo-capture/app.py
```

Python roda **dentro do browser** via Pyodide. A câmera é acessada diretamente por `navigator.mediaDevices` via FFI, sem round-trip de rede.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/photo-capture/app.py
```

Python roda no servidor; o `ProxyBridge` serializa o `native_call` e o envia ao cliente pelo WebSocket. O cliente JS captura a foto e devolve o `native_result` com os bytes base64. O servidor desserializa, cria o `Photo` e continua o handler.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Título "Camera Capture" + subtítulo + botão **Capture**
    2. Clique **Capture** → spinner aparece imediatamente (fase CAPTURING)
    3. Autorize a câmera no browser → card com prévia aparece (fase CAPTURED)
    4. Badges exibem formato (`image/jpeg`), largura e altura em pixels
    5. Clique **Clear** → volta ao estado IDLE
    6. Clique **Capture** e **negue** a permissão → card de erro com mensagem (fase ERROR)
    7. Clique **Try again** → inicia nova tentativa

---

## Testando sem câmera

Um dos pontos fortes do design deste exemplo é que você pode testar **todos os caminhos do ciclo de vida sem uma câmera real** e sem instalar nenhum bridge.

### Opção 1 — Injetando um callable falso

A forma mais simples: passe um `capture` customizado ao criar `PhotoState`.

```python
import asyncio
import base64
import pytest
from examples_photo_capture import make_state, view, Phase
from tempestweb._core import App, build
from tempestweb.native.camera import Photo

_FAKE_B64 = base64.b64encode(b"fake-image-bytes").decode()
_FAKE_PHOTO = Photo(
    mime_type="image/png", width=640, height=480, data_base64=_FAKE_B64
)

async def fake_capture() -> Photo:
    return _FAKE_PHOTO

def test_success_path() -> None:
    state = make_state()
    state.capture = fake_capture  # injeção direta

    app = App(state=state, view=view, apply_patches=lambda _: None)
    asyncio.run(view(app).on_click())  # localiza e dispara o handler
    assert app.state.phase is Phase.CAPTURED
    assert app.state.photo.width == 640
```

### Opção 2 — Instalando um `FakeBridge` (integração)

Para testes de integração que exercem o caminho real `native.camera.capture →  send_native_call → bridge.call`, instale um bridge falso com `install_bridge`/`uninstall_bridge`:

```python
from typing import Any
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.camera import Photo
import base64

_PNG_1X1_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


class FakeBridge:
    """Scripted FFI bridge — retorna uma foto PNG 640x480 fixa."""

    def __init__(self, *, fail: bool = False) -> None:
        self.last_envelope: dict[str, Any] | None = None
        self._fail = fail

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.last_envelope = envelope
        if self._fail and envelope.get("capability") == "camera.capture":
            return {"ok": False, "error": "permission_denied", "message": "Camera denied"}
        if envelope.get("capability") == "camera.capture":
            return {
                "ok": True,
                "value": {
                    "mime_type": "image/png",
                    "width": 640,
                    "height": 480,
                    "data_base64": _PNG_1X1_B64,
                },
            }
        return {"ok": False, "error": "unavailable", "message": "no handler"}


import pytest

@pytest.fixture(autouse=True)
def _clean_bridge():
    uninstall_bridge()
    yield
    uninstall_bridge()

@pytest.fixture()
def fake_bridge():
    bridge = FakeBridge()
    install_bridge(bridge)
    return bridge

@pytest.fixture()
def failing_bridge():
    bridge = FakeBridge(fail=True)
    install_bridge(bridge)
    return bridge
```

!!! info "Por que `autouse=True` no `_clean_bridge`?"
    Garante que nenhum bridge "vaze" entre testes. Mesmo que um teste falhe abruptamente no meio, o `yield` do fixture assegura que `uninstall_bridge()` seja chamado no teardown.

### Os 6 testes da suíte oficial

A suíte em `tests/unit/test_example_photo_capture.py` cobre:

| Teste | O que verifica |
|---|---|
| `test_build_without_bridge_yields_idle_tree` | `build(view(app))` funciona sem nenhum bridge instalado (render inicial é puro) |
| `test_idle_state_has_capture_button` | Fase IDLE contém widget com `key="capture"` |
| `test_capture_handler_transitions_to_captured` | `do_capture()` com bridge OK → fase CAPTURED, `photo.width == 640` |
| `test_capture_handler_surfaces_permission_error` | `do_capture()` com bridge `fail=True` → fase ERROR, `error` contém `"permission_denied"` |
| `test_photo_to_bytes_round_trips` | `Photo.to_bytes()` decodifica base64 corretamente |
| `test_photo_is_frozen_after_construction` | `Photo` é imutável (Pydantic frozen model) |

---

## Verificação automatizada ✅

Rode os checks completos antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes (inclui os 6 do photo-capture)
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno está explicitamente anotado.

---

## Como funciona por dentro

### O ciclo de atualização assíncrono

```
Clique no botão "Capture"
      │
      ▼
do_capture() (handler async)
      │
      ├─► app.set_state(phase = CAPTURING)  ←── re-render: spinner aparece
      │
      ▼
await app.state.capture()
      │
      ├── Modo A: FFIBridge.call(envelope)
      │     └─► window.__tempestweb_native__(envelope) [JS, in-process]
      │             └─► navigator.mediaDevices.getUserMedia(...)
      │
      └── Modo B: ProxyBridge.call(envelope)
            └─► envia native_call pelo WebSocket
                    └─► client/native/camera.js
                            └─► navigator.mediaDevices.getUserMedia(...)
                    └─► recebe native_result pelo WebSocket
      │
      ├── NativeError? ──► app.set_state(phase = ERROR)   ←── re-render: card de erro
      └── OK           ──► app.set_state(phase = CAPTURED) ←── re-render: card com foto
```

### Por que o render inicial não precisa de bridge?

`view(app)` apenas **lê** `app.state` e constrói widgets — ela nunca chama capabilities. `do_capture` só é executado quando o usuário **clica** no botão, muito depois do render inicial. Por isso `build(view(app))` funciona em qualquer contexto Python, sem browser, sem bridge.

### `ImageFit.COVER` — como a foto é ajustada

`Image(fit=ImageFit.COVER, ...)` instrui o renderizador a cobrir o container (`320 × 240`) recortando as bordas se necessário — o mesmo comportamento de `object-fit: cover` no CSS. Isso garante que a prévia tenha sempre dimensões fixas, independentemente do tamanho real da foto capturada.

### `Divider` — separação semântica

`Divider` é um componente sem filhos que o renderizador traduz em `<hr>`. Usado entre a prévia da foto e os badges de metadados para criar separação visual sem `padding` extra.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar um **ciclo de vida assíncrono** com `StrEnum` (IDLE → CAPTURING → CAPTURED | ERROR)
- ✅ Usar **dependency injection** no estado para manter a `view` testável sem câmera real
- ✅ Escrever um handler `async` que realiza **múltiplas transições de estado** em sequência
- ✅ Capturar `NativeError` separadamente para tratar permissões negadas com elegância
- ✅ Construir uma prévia de imagem com URI `data:` usando `Image` + `ImageFit.COVER`
- ✅ Usar `Card` + `Divider` + `Row` para compor um card de resultado com metadados
- ✅ Instalar um `FakeBridge` em testes para exercer o caminho completo sem browser

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um botão **Switch Camera** que alterna `facing` entre `"environment"` e `"user"`
- 💡 Use `native.http.upload` para enviar a foto capturada para um endpoint de API
- 💡 Explore [Clima (HTTP + geolocalização)](./weather-native.md) — outro exemplo de capability nativa com o mesmo padrão de bridge
- 💡 Leia o [contrato de wire format](../wire-contract.md) para entender como `native_call`/`native_result` trafegam no Modo B
