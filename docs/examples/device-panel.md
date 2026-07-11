# Painel do dispositivo — Capacidades Tier 1 📱

Um pequeno painel de controle que liga **quatro** capacidades nativas do
[Trilho T](../native-reference.md) a botões: vibrar o aparelho, manter a tela acesa,
ir para tela cheia e ler o estado da conexão. Uma tela, quatro Web APIs, o **mesmo**
Python nos dois modos. 🚀

## O que você vai construir

- 🔵 Botão **Buzz** — vibra num padrão (`native.vibration`)
- 🟢 Botão **Keep awake** — segura/libera um wake lock de tela (`native.wakelock`)
- 🟣 Botão **Fullscreen** — entra em tela cheia (`native.fullscreen`)
- 🟠 Botão **Network** — lê o tipo de conexão e o status online (`native.network`)
- 💬 Duas linhas de status refletindo a última ação e o resumo de rede

!!! info "Uma vitrine do Tier 1"
    O Tier 1 do Trilho T é o conjunto de capacidades **universais** — suporte amplo,
    baratas, alto valor. Este exemplo pega quatro delas e mostra que cada uma é só
    um `await native.<grupo>.<verbo>()` dentro de um handler. Sem JavaScript.

## O app completo

Aqui está o `examples/device-panel/app.py` na íntegra, pronto para copiar:

```python
"""Device panel — Tier-1 web-platform capabilities in one screen.

The same ``view`` runs unchanged in both interactive modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A small control panel wiring several of the new ``native`` capabilities to
buttons: buzz the device (``vibration``), keep the screen awake
(``wakelock``), go fullscreen (``fullscreen``), and read the connection and
storage-quota state (``network`` / ``quota``). Each is a typed Python awaitable
that resolves the same way in Mode A (in-process) and Mode B (proxied to the
browser and back) — the app code never knows the difference.

The initial mount only reads state, so ``build(view(app))`` is green with no
native bridge installed; the async handlers call the capabilities, and the test
drives them through a scripted bridge.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Text
from tempestweb import native


@dataclass
class PanelState:
    """State for the device panel.

    Attributes:
        status: A short human-readable line describing the last action.
        awake: Whether a screen wake lock is currently held.
        network: The last connection summary read from ``network.state``.
    """

    status: str = "ready"
    awake: bool = False
    network: str = ""


def make_state() -> PanelState:
    """Build the initial state.

    Returns:
        A fresh :class:`PanelState`.
    """
    return PanelState()


def view(app: App[PanelState]) -> Widget:
    """Render the panel and wire each button to a native capability.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def buzz() -> None:
        await native.vibration.vibrate([100, 50, 100])
        app.set_state(lambda s: setattr(s, "status", "buzzed"))

    async def toggle_awake() -> None:
        if app.state.awake:
            app.set_state(lambda s: setattr(s, "status", "screen released"))
            app.set_state(lambda s: setattr(s, "awake", False))
        else:
            await native.wakelock.request()
            app.set_state(lambda s: setattr(s, "status", "screen kept awake"))
            app.set_state(lambda s: setattr(s, "awake", True))

    async def go_fullscreen() -> None:
        active = await native.fullscreen.enter()
        app.set_state(lambda s: setattr(s, "status", f"fullscreen={active}"))

    async def read_network() -> None:
        state = await native.network.state()
        summary = f"{state.effective_type} · online={state.online}"
        app.set_state(lambda s: setattr(s, "network", summary))
        app.set_state(lambda s: setattr(s, "status", "network read"))

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Status: {app.state.status}", key="status"),
            Text(content=f"Network: {app.state.network or '—'}", key="network"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Button(label="Buzz", on_click=buzz, key="buzz"),
                    Button(label="Keep awake", on_click=toggle_awake, key="awake"),
                    Button(label="Fullscreen", on_click=go_fullscreen, key="fs"),
                    Button(label="Network", on_click=read_network, key="net"),
                ],
            ),
        ],
    )
```

## Peça por peça

### O estado

```python
@dataclass
class PanelState:
    status: str = "ready"
    awake: bool = False
    network: str = ""
```

Três campos simples: uma linha de `status`, um booleano `awake` para lembrar se o
wake lock está de pé, e um `network` com o resumo da última leitura. O render
inicial só **lê** esses campos — nunca chama uma capacidade —, então
`build(view(app))` é verde **sem nenhuma bridge instalada**. Essa é a mesma
disciplina dos outros exemplos nativos: o mount não depende de browser.

### Os handlers — um `await` por capacidade

Cada botão liga a um handler `async` definido **dentro** de `view()` (para capturar
o `app`). Repare como cada um é só uma linha de capacidade + `set_state`:

```python
async def buzz() -> None:
    await native.vibration.vibrate([100, 50, 100])
    app.set_state(lambda s: setattr(s, "status", "buzzed"))
```

`vibration.vibrate` recebe um padrão on/off em milissegundos — `[100, 50, 100]`
vibra 100 ms, pausa 50 ms, vibra mais 100 ms. É fire-and-forget: não retorna valor.

```python
async def toggle_awake() -> None:
    if app.state.awake:
        app.set_state(lambda s: setattr(s, "status", "screen released"))
        app.set_state(lambda s: setattr(s, "awake", False))
    else:
        await native.wakelock.request()
        app.set_state(lambda s: setattr(s, "status", "screen kept awake"))
        app.set_state(lambda s: setattr(s, "awake", True))
```

`wakelock.request()` mantém a tela acesa e devolve um **id opaco** (que uma versão
mais completa guardaria para chamar `wakelock.release(id)`). Aqui, para manter o
exemplo enxuto, o toggle apenas alterna o estado visual.

```python
async def go_fullscreen() -> None:
    active = await native.fullscreen.enter()
    app.set_state(lambda s: setattr(s, "status", f"fullscreen={active}"))
```

`fullscreen.enter()` retorna um `bool` — se o documento está em tela cheia depois da
chamada. Bom hábito: refletir o resultado real no estado, não presumir sucesso.

```python
async def read_network() -> None:
    state = await native.network.state()
    summary = f"{state.effective_type} · online={state.online}"
    app.set_state(lambda s: setattr(s, "network", summary))
    app.set_state(lambda s: setattr(s, "status", "network read"))
```

`network.state()` devolve um `NetworkState` tipado (`online`, `effective_type`,
`downlink`, `rtt`, `save_data`). Aqui montamos um resumo curto com dois campos.

!!! tip "A mesma linha, dois mecanismos"
    Nenhum handler nomeia um transporte. No Modo A cada `await native.…` resolve
    **in-process** via `FFIBridge`; no Modo B ele é **proxiado** por um round-trip
    pelo WebSocket (`ProxyBridge`). O código é idêntico — é isso que o Trilho T
    entrega.

### A árvore de widgets

```python
return Column(
    style=Style(gap=10.0, padding=Edge.all(16)),
    children=[
        Text(content=f"Status: {app.state.status}", key="status"),
        Text(content=f"Network: {app.state.network or '—'}", key="network"),
        Row(
            style=Style(gap=6.0),
            children=[
                Button(label="Buzz", on_click=buzz, key="buzz"),
                Button(label="Keep awake", on_click=toggle_awake, key="awake"),
                Button(label="Fullscreen", on_click=go_fullscreen, key="fs"),
                Button(label="Network", on_click=read_network, key="net"),
            ],
        ),
    ],
)
```

Duas linhas de `Text` derivadas do estado, e uma `Row` com os quatro botões. Cada
`Button` recebe seu handler `async` direto em `on_click`. As `key`s estáveis mantêm
o reconciliador (e os testes) precisos.

## Rodando o exemplo ▶

Este exemplo roda nos **Modos A/B** — o mesmo `app.py`, sem mudar uma linha:

```bash
tempestweb dev --mode wasm    examples/device-panel   # Python no browser (Pyodide)
tempestweb dev --mode server  examples/device-panel   # Python no servidor (FastAPI + WS)
```

!!! warning "Contexto seguro e gesto do usuário"
    `fullscreen.enter()`, `wakelock.request()` e `vibration.vibrate()` só funcionam
    a partir de um **gesto real** do usuário (o clique no botão conta) e, em
    produção, sob **HTTPS**. Em `localhost` com o dev server tudo funciona. Fora de
    contexto seguro, a bridge devolve um `NativeError` (`insecure_context` ou
    `permission_denied`) — trate como fluxo normal.

!!! check "Verificação"
    Em qualquer modo você deve ver duas linhas de status e quatro botões. Clicar:

    1. **Buzz** → o aparelho vibra (em hardware compatível) e o status vira `buzzed`.
    2. **Keep awake** → status `screen kept awake`; clicar de novo → `screen released`.
    3. **Fullscreen** → a página entra em tela cheia; status `fullscreen=True`.
    4. **Network** → a linha Network mostra algo como `4g · online=True`.

## Recap

- Quatro capacidades **Tier 1** (`vibration`, `wakelock`, `fullscreen`, `network`)
  ligadas a quatro botões, cada uma um `await native.<grupo>.<verbo>()`.
- O render inicial só **lê** o estado, então `build(view(app))` é verde **sem
  bridge** — o padrão testável dos exemplos nativos.
- **Reflita o retorno real** no estado (`fullscreen.enter()` devolve `bool`), em vez
  de presumir sucesso.
- O **mesmo** código roda no Modo A (in-process) e no Modo B (proxiado) — o handler
  nunca sabe qual bridge está instalada.

## Próximos passos

- 💡 Guarde o id de `wakelock.request()` no estado e chame `wakelock.release(id)` no
  toggle, para liberar de verdade.
- 💡 Adicione um botão que **observa** a rede em stream com
  `native.network.watch()` — veja o [canal de eventos nativo](../native-events.md).
- 💡 Explore o catálogo completo na
  [Referência de capacidades nativas](../native-reference.md).
- 💡 Compare com o [Copiar e compartilhar](clipboard-share.md), que injeta as
  capacidades no estado para testar sem browser.
