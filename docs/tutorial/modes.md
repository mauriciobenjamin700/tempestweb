# 4. Rodando os modos

!!! abstract "O que você vai aprender"
    Como rodar o **mesmo** `app.py` — sem mudar uma linha — nos três modos de
    execução, e como escolher o modo certo para cada requisito.

Você construiu o counter inteiro: [árvore](view.md), [estado](state.md) e
[patches](patches.md). Agora o pagamento da promessa central do tempestweb: o
**mesmo** `examples/counter/app.py` roda em **Modo A (WASM)**, **Modo B
(servidor)** e **Modo C (transpile)** — sem mudar uma linha. 🎯

## O app não nomeia transporte

Releia o app completo. Note o que **não** está lá: nenhum `import websocket`,
nenhum `import pyodide`, nenhuma menção a "browser" ou "servidor".

```python
"""Counter — the canonical tempestweb example."""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


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

## Modo C — Python transcrito para JavaScript (transpile)

No Modo C, não há Python vivo em lugar nenhum. Um compilador transcreve a **camada
de app** (o seu `view`/`state`/handlers) para **JavaScript nativo** no build, e o
resultado é um bundle 100% estático:

=== "Comando"

    ```bash
    tempestweb build --mode transpile examples/counter   # gera dist/transpile/
    tempestweb dev   --mode transpile examples/counter    # com livereload
    ```

=== "O que acontece"

    1. O compilador lê o `app.py` e emite `app.gen.js` — JS nativo.
    2. No browser, o runtime segura o estado e roda `view()` **em JavaScript**.
    3. O `diff` roda nativo no browser; não há transporte nem servidor.
    4. O **mesmo** `client/dom.js` aplica os patches no DOM.

!!! tip "Modo C é o alvo perfeito para PWA e SEO"
    Como o bundle é estático e sem Python, o first-paint é imediato e o `build`
    já emite a camada **PWA instalável + offline** de fábrica. É a página
    [Modo C — transpile](../transpile.md) que aprofunda o fluxo completo. 🚀

## Lado a lado

| | Modo A — WASM | Modo B — Servidor | Modo C — transpile |
|---|---|---|---|
| Onde o Python roda | No browser (Pyodide) | No servidor (FastAPI) | **Em lugar nenhum** (vira JS) |
| Como os patches chegam | `pyodide.ffi` (em-processo) | WebSocket / SSE (rede) | `diff` em JS, em-processo |
| Estado | No browser | No servidor, isolado por conexão | No browser (JS) |
| Offline | Pleno após o load | Parcial (cache read-only + fila) | Pleno (bundle estático) |
| Latência por interação | Zero round-trip | Um round-trip de rede | Zero round-trip |
| SEO / first-paint | Fraco (bundle WASM) | Forte (HTML do servidor) | **Ótimo** (bundle estático) |

!!! warning "Escolha o modo pelo requisito, não pelo gosto"
    Precisa de SEO, first-paint rápido e um site/PWA estático sem servidor? →
    **Modo C**. Precisa rodar lógica sensível ou estado central no servidor? →
    **Modo B**. Quer Python vivo no browser para prototipar? → **Modo A**. O app é
    o mesmo; só o `--mode` muda.

## Recap

- O `app.py` **nunca nomeia um transporte** — `view`/`state`/handlers são
  portáveis nos três modos.
- **Modo A** roda Python no browser via Pyodide; patches via `pyodide.ffi`.
- **Modo B** roda Python no servidor (FastAPI); patches via WebSocket/SSE.
- **Modo C** transcreve o app para JS nativo; `diff` em-processo, bundle estático.
- O **cliente JS e o renderizador são os mesmos**; só o modo muda.

🎉 Você terminou o tutorial! Você construiu o counter e entende o contrato de
fronteira de ponta a ponta. Para ir além, mergulhe no
[Modo C — transpile](../transpile.md), na camada [PWA e offline](../pwa.md), nas
[capacidades nativas](../capabilities.md) e na
[observabilidade](../observability.md).
