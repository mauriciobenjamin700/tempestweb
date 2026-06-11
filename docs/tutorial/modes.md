# 4. Rodando os dois modos

Você construiu o counter inteiro: [árvore](view.md), [estado](state.md) e
[patches](patches.md). Agora o pagamento da promessa central do tempestweb: o
**mesmo** `examples/counter/app.py` roda em **Modo A (WASM)** e **Modo B
(servidor)** — sem mudar uma linha. 🎯

## O app não nomeia transporte

Releia o app completo. Note o que **não** está lá: nenhum `import websocket`,
nenhum `import pyodide`, nenhuma menção a "browser" ou "servidor".

```python
"""Counter — the canonical tempestweb example."""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

!!! check "O app é agnóstico de transporte"
    `view`, `make_state` e os handlers são **100% portáveis**. A escolha de modo é
    feita pela CLI, fora do app. Essa é a costura única do projeto.

## Modo A — Python no browser (WASM)

No Modo A, seu Python roda **dentro da aba** via Pyodide. A CLI empacota o app +
o cliente JS num bundle estático:

=== "Comando"

    ```bash
    tempestweb build --mode wasm examples/counter/app.py
    tempestweb dev   --mode wasm examples/counter/app.py   # com hot-reload
    ```

=== "O que acontece"

    1. O Pyodide carrega o interpretador Python no browser.
    2. `view()` roda em-processo; o `diff` produz patches.
    3. Os patches chegam ao cliente por **`pyodide.ffi`** — chamada de função,
       sem rede.
    4. `client/dom.js` aplica os patches no DOM.

!!! tip "Modo A é offline pleno"
    Depois do load inicial, tudo roda no browser — sem servidor. É o alvo natural
    para [PWA e offline](../pwa.md). O custo é o cold-start do bundle WASM (que o
    service worker do Trilho P resolve via precache).

## Modo B — Python no servidor (FastAPI)

No Modo B, seu Python roda **no servidor** e fala com um cliente JS fino por
WebSocket (ou SSE). Análogo ao Phoenix LiveView:

=== "Comando"

    ```bash
    tempestweb dev --mode server examples/counter/app.py
    # serve em http://127.0.0.1:8000
    ```

=== "O que acontece"

    1. O FastAPI hospeda o app; cada conexão tem sua sessão asyncio isolada.
    2. O usuário clica → o cliente envia `{ "kind": "event", "data": {...} }`.
    3. O servidor resolve o handler, roda `view()`, faz `diff`.
    4. O servidor envia `{ "kind": "patches", "data": [...] }` de volta.
    5. O **mesmo** `client/dom.js` aplica os patches.

!!! info "O cliente JS é o mesmo nos dois modos"
    Só a implementação de transporte difere: `transport-wasm.js` (Modo A) versus
    `transport-ws.js` / `transport-sse.js` (Modo B). O renderizador
    (`client/dom.js`, `client/style.js`) é **um só**.

## Lado a lado

| | Modo A — WASM | Modo B — Servidor |
|---|---|---|
| Onde o Python roda | No browser (Pyodide) | No servidor (FastAPI) |
| Transporte de patches | `pyodide.ffi` (em-processo) | WebSocket / SSE (rede) |
| Estado | No browser | No servidor, isolado por conexão |
| Offline | Pleno após o load | Parcial (cache read-only + fila) |
| Latência por interação | Zero round-trip | Um round-trip de rede |
| SEO / first-paint | Fraco (bundle WASM) | Forte (HTML do servidor) |

!!! warning "Escolha o modo pelo requisito, não pelo gosto"
    Precisa de SEO, first-paint rápido, ou rodar lógica sensível no servidor? →
    **Modo B**. Precisa de offline pleno, zero infra de servidor, ou app
    instalável puro-cliente? → **Modo A**. O app é o mesmo; só o `--mode` muda.

## Recap

- O `app.py` **nunca nomeia um transporte** — `view`/`state`/handlers são
  portáveis.
- **Modo A** roda Python no browser via Pyodide; patches via `pyodide.ffi`.
- **Modo B** roda Python no servidor (FastAPI); patches via WebSocket/SSE.
- O **cliente JS e o renderizador são os mesmos**; só a impl de transporte muda.

🎉 Você terminou o tutorial! Você construiu o counter e entende o contrato de
fronteira de ponta a ponta. Para ir além, explore as
[capacidades nativas](../capabilities.md), a camada [PWA e offline](../pwa.md) e
a [observabilidade](../observability.md).
