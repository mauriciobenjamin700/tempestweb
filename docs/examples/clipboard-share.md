# Copy & Share — Capacidades Nativas 📋

Acesse o **clipboard** e o **share sheet** do sistema operacional direto do Python tipado — e aprenda como o tempestweb conecta código Python a APIs nativas do browser.

---

## O que você vai construir

Um demo de cópia e compartilhamento com:

- 📄 Um trecho de texto exibido na tela
- 📋 Botão **Copy** que escreve o texto no clipboard do SO
- 🔗 Botão **Share** que abre o share sheet nativo do browser
- ⏳ Um **Spinner** exibido enquanto a operação está em andamento
- 💬 Texto de status que reflete o resultado: copiado, compartilhado, cancelado, não suportado ou erro

!!! note "Nota — o que são capacidades nativas?"
    Capacidades nativas são Web APIs do browser (Clipboard API, Web Share API, Geolocation API etc.) acessadas a partir do Python tipado. O tempestweb roteia cada chamada para o browser correto — seja o browser rodando Python diretamente (Modo A / WASM) ou o browser separado do servidor Python (Modo B / WebSocket).

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

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/clipboard-share
touch examples/clipboard-share/app.py
```

---

## Passo 1 — Entendendo a bridge nativa

Antes de escrever código, é importante entender **por que** existe uma bridge.

O Python não tem acesso direto ao clipboard ou ao share sheet — esses são recursos do browser. O tempestweb resolve isso através de uma `NativeBridge`, que é a única diferença entre os dois modos de execução:

| Modo | Bridge instalada | Como funciona |
|---|---|---|
| **A (WASM)** | `FFIBridge` | Chama `client/native/*.js` diretamente, in-process, sem rede |
| **B (servidor)** | `ProxyBridge` | Serializa a chamada, envia ao browser pelo WebSocket, aguarda o resultado |

!!! warning "Atenção — bridge obrigatória em runtime"
    As funções `clipboard.write` e `share.share` lançam `BrowserUnavailableError` se nenhuma bridge estiver instalada no momento da chamada. Em runtime (Modo A ou B) a bridge é instalada automaticamente pelo bootstrap do tempestweb. **Você não precisa chamar `install_bridge` na sua aplicação.** Você só chama `install_bridge` / `uninstall_bridge` em **testes** para injetar uma bridge falsa.

No diagrama abaixo, o `NativeBridge` é a única peça que muda entre os modos — a função `view` não sabe e não precisa saber qual bridge está instalada:

```
view(app)
    │
    └── await clipboard.write(text)
              │
              └── send_native_call("clipboard.write", ...)
                        │
                        └── current_bridge().call(envelope)   ← SEAM
                                  │
                          ┌───────┴────────┐
                          │                │
                     FFIBridge        ProxyBridge
                  (Modo A: in-proc)  (Modo B: WebSocket)
                          │                │
                    client/native/    client/native/
                    clipboard.js      clipboard.js
                          │                │
                  navigator.clipboard.writeText(...)
```

---

## Passo 2 — Definindo os tipos e o estado

O exemplo usa injeção de dependência para que os testes possam trocar as funções reais por fakes.

Definimos dois tipos de callable — `Copier` e `Sharer` — e armazenamos a função concreta como campo do estado:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import clipboard
from tempestweb.native.share import ShareOutcome, ShareResult
from tempestweb.native.share import share as _native_share

# ---------------------------------------------------------------------------
# Injected capability types
# ---------------------------------------------------------------------------

#: A coroutine that writes text to the clipboard. Injected for testability.
Copier = Callable[[str], Awaitable[None]]

#: A coroutine that opens the share sheet. Injected for testability.
Sharer = Callable[..., Awaitable[ShareResult]]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: The snippet shown to the user and offered for copy / share.
SNIPPET: str = "tempestweb — write UIs in typed Python, run them everywhere."


class Phase(StrEnum):
    """Lifecycle phase of the clipboard-share interaction.

    Attributes:
        IDLE: Nothing has been attempted yet.
        BUSY: A capability call is in flight.
        COPIED: The clipboard write succeeded.
        SHARED: The share sheet completed.
        ERROR: The capability raised an error.
    """

    IDLE = "idle"
    BUSY = "busy"
    COPIED = "copied"
    SHARED = "shared"
    ERROR = "error"


@dataclass
class ClipShareState:
    """Application state for the clipboard-share demo.

    Attributes:
        phase: Current lifecycle phase.
        share_outcome: The ShareOutcome from the last share attempt, or
            None if no share has been tried.
        error: Human-readable error message shown when phase is ERROR.
        copy: Injected clipboard-write coroutine (real default is the native cap).
        share_fn: Injected share coroutine (real default is the native cap).
    """

    phase: Phase = Phase.IDLE
    share_outcome: ShareOutcome | None = None
    error: str = ""
    copy: Copier = field(default=clipboard.write)
    share_fn: Sharer = field(default=_native_share)


def make_state() -> ClipShareState:
    """Build the initial, idle clipboard-share state.

    Returns:
        A fresh ClipShareState.
    """
    return ClipShareState()
```

!!! tip "Dica — injeção de dependência via campo do dataclass"
    Ao guardar `copy` e `share_fn` como campos com defaults reais, você consegue duas coisas ao mesmo tempo:

    1. **Em produção**, `make_state()` cria um estado com as funções nativas reais — zero configuração extra.
    2. **Em testes**, você substitui os callables por fakes sem precisar de monkey-patching: basta passar `copy=fake_copy` ao construir o estado.

    Esse padrão é especialmente valioso quando a função real precisaria de uma bridge instalada para não lançar exceção.

Veja como a máquina de estados evolui conforme o usuário age:

```
IDLE ──────── clicar Copy ──────► BUSY ──── sucesso ──► COPIED
  │                                  │
  │           clicar Share           └──── erro ──────► ERROR
  └─────────────────────────────► BUSY ──── sucesso ──► SHARED
                                       └──── erro ──────► ERROR
```

---

## Passo 3 — Os handlers assíncronos

Os handlers ficam **dentro de `view()`** porque precisam capturar o `app` do escopo externo. Cada um segue o mesmo padrão de três etapas:

1. Transiciona para `BUSY` imediatamente (feedback visual).
2. `await` a capacidade nativa.
3. Transiciona para o estado final (`COPIED`, `SHARED` ou `ERROR`).

```python
async def do_copy() -> None:
    """Copy the snippet to the OS clipboard.

    Transitions: IDLE/ERROR -> BUSY -> COPIED | ERROR.
    """
    app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
    try:
        await app.state.copy(SNIPPET)
    except Exception as exc:  # noqa: BLE001 — surface to UI
        msg = str(exc)

        def _on_copy_error(s: ClipShareState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_copy_error)
        return

    app.set_state(lambda s: setattr(s, "phase", Phase.COPIED))


async def do_share() -> None:
    """Open the OS share sheet.

    Transitions: IDLE/ERROR -> BUSY -> SHARED (outcome stored) | ERROR.
    """
    app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
    try:
        result: ShareResult = await app.state.share_fn(
            title="tempestweb",
            text=SNIPPET,
            url="https://github.com/tempest-framework/tempestweb",
        )
    except Exception as exc:  # noqa: BLE001 — surface to UI
        msg = str(exc)

        def _on_share_error(s: ClipShareState) -> None:
            s.phase = Phase.ERROR
            s.error = msg

        app.set_state(_on_share_error)
        return

    def _on_shared(s: ClipShareState) -> None:
        s.phase = Phase.SHARED
        s.share_outcome = result.outcome

    app.set_state(_on_shared)
```

!!! info "Por que capturar `Exception` genérica aqui?"
    Em produção a função de share pode lançar `NativeError` (da bridge) ou qualquer exceção de rede. Capturar `Exception` e exibir a mensagem na UI é o comportamento correto para um demo: o usuário vê o que aconteceu. Em apps de produção você pode ser mais seletivo e separar os tipos de erro.

!!! tip "Dica — `ShareOutcome` não é uma exceção"
    `ShareOutcome.CANCELLED` e `ShareOutcome.UNSUPPORTED` são retornados como valores normais dentro de `ShareResult`, nunca como exceções. A Web Share API degrada graciosamente: se o browser não suporta `navigator.share`, o JS retorna `{"outcome": "unsupported"}` em vez de lançar um erro.

---

## Passo 4 — O texto de status

O texto de status é derivado do `phase` e do `share_outcome` atuais. É calculado dentro de `view()` a cada render — zero estado extra:

```python
phase = app.state.phase

if phase is Phase.IDLE:
    status_text = "Choose an action below."
elif phase is Phase.BUSY:
    status_text = "Working…"
elif phase is Phase.COPIED:
    status_text = "Copied to clipboard!"
elif phase is Phase.SHARED:
    outcome = app.state.share_outcome
    if outcome is ShareOutcome.SHARED:
        status_text = "Shared successfully."
    elif outcome is ShareOutcome.CANCELLED:
        status_text = "Share cancelled."
    else:
        # UNSUPPORTED — Web Share API missing in this browser
        status_text = "Sharing is not supported in this browser."
else:
    # ERROR
    status_text = f"Error: {app.state.error}"
```

| `phase` | `share_outcome` | Texto exibido |
|---|---|---|
| `IDLE` | — | `Choose an action below.` |
| `BUSY` | — | `Working…` |
| `COPIED` | — | `Copied to clipboard!` |
| `SHARED` | `SHARED` | `Shared successfully.` |
| `SHARED` | `CANCELLED` | `Share cancelled.` |
| `SHARED` | `UNSUPPORTED` | `Sharing is not supported in this browser.` |
| `ERROR` | — | `Error: <mensagem>` |

---

## Passo 5 — Montando a árvore de widgets

A linha de ação exibe um `Spinner` quando `BUSY`, ou os dois botões nos outros estados. Isso elimina cliques duplos sem precisar de um campo `disabled` separado:

```python
is_busy = phase is Phase.BUSY
action_children: list[Widget] = []

if is_busy:
    action_children.append(Spinner(key="spinner"))
else:
    action_children.extend(
        [
            Button(
                label="Copy",
                on_click=do_copy,
                key="copy-btn",
            ),
            Button(
                label="Share",
                on_click=do_share,
                key="share-btn",
            ),
        ]
    )

actions: Widget = Row(
    style=Style(gap=8.0),
    children=action_children,
    key="actions",
)

return Column(
    style=Style(gap=16.0, padding=Edge.all(20.0)),
    children=[
        Text(content="Copy & Share", style=Style(font_size=22.0), key="title"),
        Text(
            content=SNIPPET,
            style=Style(font_size=14.0),
            key="snippet",
        ),
        actions,
        Text(content=status_text, key="status"),
    ],
)
```

!!! tip "Dica — Spinner como proteção contra duplo clique"
    Substituir os botões por um `Spinner` durante `BUSY` é uma proteção natural: não há botão para clicar, logo não há como disparar uma segunda operação simultânea. É mais simples e mais seguro do que manter um campo booleano `loading` separado do `phase`.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Copy & share — exercises the clipboard and share native capabilities.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The demo presents a short text snippet alongside two action buttons:

* **Copy** — writes the snippet to the OS clipboard via
  ``native.clipboard.write``.  The action status is stored in state so the UI
  reflects whether the write succeeded, failed or is still pending.
* **Share** — opens the platform share sheet via ``native.share.share`` and
  renders the :class:`~tempestweb.native.share.ShareOutcome` back to the user:
  ``shared``, ``cancelled``, or ``unsupported`` (the API does not exist in
  the current browser).

Both capability callables are **injected into** :class:`ClipShareState` with
real defaults so that:

1. ``build(view(app))`` is green with **no bridge installed** — the initial
   mount only reads state; it never calls the capabilities.
2. Tests swap in a ``FakeBridge`` and drive the async handlers end-to-end,
   asserting real state transitions.

State machine
-------------
* ``Phase.IDLE``    — nothing has been attempted yet.
* ``Phase.BUSY``    — a capability call is in flight (spinner or disabled feedback).
* ``Phase.COPIED``  — clipboard write succeeded.
* ``Phase.SHARED``  — share sheet completed (outcome stored separately).
* ``Phase.ERROR``   — the capability raised :class:`~tempestweb.native.NativeError`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import clipboard
from tempestweb.native.share import ShareOutcome, ShareResult
from tempestweb.native.share import share as _native_share

# ---------------------------------------------------------------------------
# Injected capability types
# ---------------------------------------------------------------------------

#: A coroutine that writes text to the clipboard. Injected for testability.
Copier = Callable[[str], Awaitable[None]]

#: A coroutine that opens the share sheet. Injected for testability.
Sharer = Callable[..., Awaitable[ShareResult]]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: The snippet shown to the user and offered for copy / share.
SNIPPET: str = "tempestweb — write UIs in typed Python, run them everywhere."


class Phase(StrEnum):
    """Lifecycle phase of the clipboard-share interaction.

    Attributes:
        IDLE: Nothing has been attempted yet.
        BUSY: A capability call is in flight.
        COPIED: The clipboard write succeeded.
        SHARED: The share sheet completed.
        ERROR: The capability raised an error.
    """

    IDLE = "idle"
    BUSY = "busy"
    COPIED = "copied"
    SHARED = "shared"
    ERROR = "error"


@dataclass
class ClipShareState:
    """Application state for the clipboard-share demo.

    Attributes:
        phase: Current lifecycle phase.
        share_outcome: The :class:`~tempestweb.native.share.ShareOutcome` from
            the last share attempt, or ``None`` if no share has been tried.
        error: Human-readable error message shown when ``phase`` is ERROR.
        copy: Injected clipboard-write coroutine (real default is the native cap).
        share_fn: Injected share coroutine (real default is the native cap).
    """

    phase: Phase = Phase.IDLE
    share_outcome: ShareOutcome | None = None
    error: str = ""
    copy: Copier = field(default=clipboard.write)
    share_fn: Sharer = field(default=_native_share)


def make_state() -> ClipShareState:
    """Build the initial, idle clipboard-share state.

    Returns:
        A fresh :class:`ClipShareState`.
    """
    return ClipShareState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[ClipShareState]) -> Widget:
    """Render the clipboard-share UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def do_copy() -> None:
        """Copy the snippet to the OS clipboard.

        Transitions: IDLE/ERROR -> BUSY -> COPIED | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            await app.state.copy(SNIPPET)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_copy_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_copy_error)
            return

        app.set_state(lambda s: setattr(s, "phase", Phase.COPIED))

    async def do_share() -> None:
        """Open the OS share sheet.

        Transitions: IDLE/ERROR -> BUSY -> SHARED (outcome stored) | ERROR.
        """
        app.set_state(lambda s: setattr(s, "phase", Phase.BUSY))
        try:
            result: ShareResult = await app.state.share_fn(
                title="tempestweb",
                text=SNIPPET,
                url="https://github.com/tempest-framework/tempestweb",
            )
        except Exception as exc:  # noqa: BLE001 — surface to UI
            msg = str(exc)

            def _on_share_error(s: ClipShareState) -> None:
                s.phase = Phase.ERROR
                s.error = msg

            app.set_state(_on_share_error)
            return

        def _on_shared(s: ClipShareState) -> None:
            s.phase = Phase.SHARED
            s.share_outcome = result.outcome

        app.set_state(_on_shared)

    # ------------------------------------------------------------------
    # Status text — reflects the last action
    # ------------------------------------------------------------------

    phase = app.state.phase

    if phase is Phase.IDLE:
        status_text = "Choose an action below."
    elif phase is Phase.BUSY:
        status_text = "Working…"
    elif phase is Phase.COPIED:
        status_text = "Copied to clipboard!"
    elif phase is Phase.SHARED:
        outcome = app.state.share_outcome
        if outcome is ShareOutcome.SHARED:
            status_text = "Shared successfully."
        elif outcome is ShareOutcome.CANCELLED:
            status_text = "Share cancelled."
        else:
            # UNSUPPORTED — Web Share API missing in this browser
            status_text = "Sharing is not supported in this browser."
    else:
        # ERROR
        status_text = f"Error: {app.state.error}"

    # ------------------------------------------------------------------
    # Action buttons row
    # ------------------------------------------------------------------

    is_busy = phase is Phase.BUSY
    action_children: list[Widget] = []

    if is_busy:
        action_children.append(Spinner(key="spinner"))
    else:
        action_children.extend(
            [
                Button(
                    label="Copy",
                    on_click=do_copy,
                    key="copy-btn",
                ),
                Button(
                    label="Share",
                    on_click=do_share,
                    key="share-btn",
                ),
            ]
        )

    actions: Widget = Row(
        style=Style(gap=8.0),
        children=action_children,
        key="actions",
    )

    # ------------------------------------------------------------------
    # Assemble the full view
    # ------------------------------------------------------------------

    return Column(
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=[
            Text(content="Copy & Share", style=Style(font_size=22.0), key="title"),
            Text(
                content=SNIPPET,
                style=Style(font_size=14.0),
                key="snippet",
            ),
            actions,
            Text(content=status_text, key="status"),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/clipboard-share/app.py
```

Python roda **dentro do browser** via Pyodide. A `FFIBridge` é instalada automaticamente pelo bootstrap do WASM e chama `client/native/clipboard.js` e `client/native/share.js` in-process.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/clipboard-share/app.py
```

Python roda no servidor; a `ProxyBridge` é instalada automaticamente pela sessão WebSocket. Cada chamada a `clipboard.write` ou `share.share` vai até o browser pelo WebSocket, o JS executa a Web API, e o resultado volta para o Python pelo mesmo canal.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Título **Copy & Share** e o snippet de texto
    2. Dois botões: **Copy** e **Share**
    3. Texto de status inicial: `Choose an action below.`
    4. Clicar **Copy** → botões somem, spinner aparece, depois: `Copied to clipboard!`
    5. Clicar **Share** → spinner → share sheet nativo do browser → `Shared successfully.` (ou `Share cancelled.` se fechar sem compartilhar)
    6. Em browsers sem Web Share API (ex.: Firefox desktop) → `Sharing is not supported in this browser.`

!!! warning "Atenção — contexto seguro"
    A Clipboard API e a Web Share API exigem **HTTPS** (ou `localhost`). Ao rodar em `localhost` com o dev server do tempestweb, tudo funciona. Em produção, certifique-se de servir sob HTTPS, caso contrário a bridge retorna um `NativeError` com código `insecure_context`.

---

## Testando com bridges falsas 🧪

Como os handlers chamam capacidades nativas, os testes não podem simplesmente importar e chamar `view()` e esperar que tudo funcione — precisariam de uma bridge real (e de um browser). A solução é a injeção de dependência: você instala uma bridge falsa antes do teste e a remove depois.

### FakeBridge — comportamento programado

```python
from typing import Any

from tempestweb.native import install_bridge, uninstall_bridge


class FakeBridge:
    """Fake native bridge for clipboard and share capabilities.

    Records the last envelope received and returns scripted responses so the
    tests run with no real browser present.

    Attributes:
        share_outcome: The share outcome string to return (default "shared").
        calls: Ordered list of capability names that were dispatched.
    """

    def __init__(self, *, share_outcome: str = "shared") -> None:
        """Initialise the bridge.

        Args:
            share_outcome: The ShareOutcome value to return from share.share.
        """
        self.share_outcome: str = share_outcome
        self.calls: list[str] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Handle a native capability call.

        Args:
            envelope: The native_call envelope dispatched by the capability wrapper.

        Returns:
            A scripted ok / value response dict.
        """
        cap: str = envelope["capability"]
        self.calls.append(cap)

        if cap == "clipboard.write":
            return {"ok": True, "value": {}}
        if cap == "share.share":
            return {"ok": True, "value": {"outcome": self.share_outcome}}

        return {"ok": False, "error": "unavailable", "message": f"no fake for {cap}"}
```

### ErrorBridge — simula falha de permissão

```python
class ErrorBridge:
    """Fake bridge that always returns an error response.

    Used to verify that the ERROR phase is surfaced correctly in the UI.
    """

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Return a permission_denied error for every call.

        Args:
            envelope: Ignored; every call returns an error.

        Returns:
            An ok: False response.
        """
        return {
            "ok": False,
            "error": "permission_denied",
            "message": "permission denied by user",
        }
```

### Os 8 testes

O suite completo de testes do exemplo cobre todos os caminhos da máquina de estados:

```python
from __future__ import annotations

from typing import Any

import pytest

from tempest_core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.share import ShareOutcome


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a list of nodes (pre-order).

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Locate a handler callable by widget key and attribute name.

    Args:
        widget: The root widget returned by view(app).
        key: The key of the target widget.
        attr: The handler attribute name (e.g. "on_click").

    Returns:
        The handler callable.

    Raises:
        AssertionError: If no matching widget/handler is found.
    """
    stack: list[Any] = [widget]
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == key:
            handler = getattr(current, attr, None)
            if handler is not None:
                return handler
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError(f"no widget with key={key!r} and handler {attr!r}")


def _status_text(node: Node) -> str:
    """Return the content prop of the status Text node.

    Args:
        node: The root IR node of the built tree.

    Returns:
        The status text string.

    Raises:
        AssertionError: If no status node is found.
    """
    for n in _walk(node):
        if n.key == "status":
            return str(n.props.get("content", ""))
    raise AssertionError("no node with key='status' found")


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:  # noqa: ANN401
    """Guarantee no bridge leaks between tests."""
    uninstall_bridge()
    yield
    uninstall_bridge()


# -- Testes ------------------------------------------------------------------


def test_initial_build_no_bridge(module: Any, app: App[Any]) -> None:
    """build(view(app)) yields a valid Node tree with no bridge installed."""
    node = build(module.view(app))
    assert isinstance(node, Node)
    assert node.type
    assert node.children


def test_initial_status_is_idle(module: Any, app: App[Any]) -> None:
    """The status Text reflects the IDLE phase on first mount."""
    node = build(module.view(app))
    assert _status_text(node) == "Choose an action below."


async def test_copy_handler_transitions_to_copied(module: Any, app: App[Any]) -> None:
    """Driving do_copy with a fake bridge transitions IDLE -> COPIED."""
    bridge = FakeBridge()
    install_bridge(bridge)

    idle_node = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "copied"
    copied_node = build(module.view(app))
    assert _status_text(copied_node) == "Copied to clipboard!"
    assert _status_text(copied_node) != _status_text(idle_node)
    assert "clipboard.write" in bridge.calls


async def test_share_handler_shared_outcome(module: Any, app: App[Any]) -> None:
    """Driving do_share with outcome 'shared' transitions IDLE -> SHARED."""
    bridge = FakeBridge(share_outcome="shared")
    install_bridge(bridge)

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.phase.value == "shared"
    assert app.state.share_outcome is ShareOutcome.SHARED
    node = build(module.view(app))
    assert _status_text(node) == "Shared successfully."
    assert "share.share" in bridge.calls


async def test_share_handler_cancelled_outcome(module: Any, app: App[Any]) -> None:
    """A cancelled share sheet transitions to SHARED with CANCELLED outcome."""
    install_bridge(FakeBridge(share_outcome="cancelled"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.CANCELLED
    node = build(module.view(app))
    assert _status_text(node) == "Share cancelled."


async def test_share_handler_unsupported_outcome(module: Any, app: App[Any]) -> None:
    """An unsupported browser returns UNSUPPORTED outcome without raising."""
    install_bridge(FakeBridge(share_outcome="unsupported"))

    handler = _find_handler(module.view(app), "share-btn", "on_click")
    await handler()

    assert app.state.share_outcome is ShareOutcome.UNSUPPORTED
    node = build(module.view(app))
    assert "not supported" in _status_text(node)


async def test_copy_error_transitions_to_error_phase(
    module: Any, app: App[Any]
) -> None:
    """A NativeError during clipboard.write transitions to the ERROR phase."""
    install_bridge(ErrorBridge())

    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()

    assert app.state.phase.value == "error"
    node = build(module.view(app))
    status = _status_text(node)
    assert status.startswith("Error:")


async def test_tree_changes_between_idle_and_copied(module: Any, app: App[Any]) -> None:
    """The rebuilt tree differs after a successful copy (diff-friendly)."""
    from tempest_core import diff

    install_bridge(FakeBridge())

    before = build(module.view(app))
    handler = _find_handler(module.view(app), "copy-btn", "on_click")
    await handler()
    after = build(module.view(app))

    patches = diff(before, after)
    assert patches, "expected at least one patch after a state transition"
```

!!! tip "Dica — `autouse=True` no `_clean_bridge`"
    O fixture `_clean_bridge` limpa a bridge antes e depois de **cada** teste usando `autouse=True`. Isso garante que um teste que esqueceu de desinstalar a bridge não contamina o próximo. É uma boa prática em qualquer suite que use `install_bridge`.

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi especificamente projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo completo de uma chamada nativa

```
1. Usuário clica "Copy"
        │
        ▼
2. do_copy() chamada
        │
        ▼
3. app.set_state(phase=BUSY) → re-render → Spinner aparece
        │
        ▼
4. await app.state.copy(SNIPPET)
        │           (= clipboard.write em produção)
        │
        ▼
5. send_native_call("clipboard.write", {"text": SNIPPET})
        │
        ▼
6. current_bridge().call(envelope)
        │
   ┌────┴──────────────────────────────┐
   │ Modo A: FFIBridge                  │ Modo B: ProxyBridge
   │ chama JS in-process               │ envia frame pelo WS
   │ (sem rede, sem round-trip)        │ aguarda native_result
   └────────────────────────────────────┘
        │
        ▼
7. navigator.clipboard.writeText(SNIPPET)  [no browser]
        │
        ▼
8. Resultado volta para o Python
        │
        ▼
9. app.set_state(phase=COPIED) → re-render → "Copied to clipboard!"
```

### Por que `Phase` é uma `StrEnum`?

`StrEnum` permite comparar `app.state.phase.value == "copied"` nos testes (string legível) **e** usar `phase is Phase.COPIED` na view (comparação de identidade, zero alocação). O valor string também é serializável nativamente em JSON — útil para logging e telemetria.

### Por que os handlers são `async`?

Capacidades nativas são operações de I/O: o Python precisa suspender enquanto o browser executa a Web API e retorna o resultado. Usar `await` é o caminho natural — o event loop asyncio do tempestweb gerencia a suspensão e retomada sem bloquear outros renders em andamento.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ O que é uma `NativeBridge` e por que ela é a única diferença entre Modo A e Modo B
- ✅ Como usar `clipboard.write` e `share.share` a partir do Python tipado
- ✅ Como modelar um fluxo assíncrono com `Phase` (IDLE → BUSY → COPIED/SHARED/ERROR)
- ✅ Como injetar capacidades no estado para tornar os handlers testáveis sem browser
- ✅ Como usar `FakeBridge` e `ErrorBridge` para testar todos os caminhos da máquina de estados
- ✅ Por que `ShareOutcome.CANCELLED` e `ShareOutcome.UNSUPPORTED` são valores normais, não exceções

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um botão **Read** que lê o texto atual do clipboard com `clipboard.read()`
- 💡 Desabilite o botão **Share** com `is_share_supported()` quando a Web Share API não estiver disponível, em vez de mostrar mensagem após o clique
- 💡 Explore o exemplo [PWA + WebPush](./notification-center.md) para ver outras capacidades nativas em ação
- 💡 Veja [Modos de execução](../tutorial/modes.md) para entender em profundidade como `FFIBridge` e `ProxyBridge` diferem
