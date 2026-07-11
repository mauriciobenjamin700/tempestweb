# Modo B ponta a ponta — Servidor FastAPI + WebSocket 🚀

Descubra como o **mesmo** `view()` que roda no browser (Modo A / Pyodide) pode ser servido de um servidor FastAPI via WebSocket — sem mudar uma linha do código da aplicação.

---

## O que você vai aprender

Neste tutorial você vai:

- 🧩 Entender a diferença entre **Modo A** (Python no browser) e **Modo B** (Python no servidor)
- 🔌 Usar `tempestweb.server.create_app` para empacotar qualquer `view` em uma aplicação FastAPI
- 🧪 Testar o servidor com `fastapi.testclient.TestClient` — sem abrir portas de rede
- 🚀 Subir o servidor real com `uvicorn.run`
- 🔍 Entender a correção de um bug de serialização em `_json_safe` que causava erro ao usar widgets com estilo (`Style`, `Edge`)

!!! note "Pré-requisito: o exemplo Counter"
    Este tutorial usa `make_state` e `view` do exemplo `examples/counter/app.py`.
    Leia [o tutorial básico](../tutorial/index.md) antes se ainda não fez isso.

---

## Por que dois modos?

O tempestweb tem uma premissa central: **o código da aplicação não conhece o transporte**. A função `view` só sabe que recebe um `App` e retorna um `Widget`. Quem decide *onde* o Python roda e *como* as patches chegam ao browser é a **camada de transporte**.

```
┌──────────────────────────────────────┐
│  view(app) → Widget                  │  ← idêntico nos dois modos
├──────────────────────────────────────┤
│  PatchTransport  (seam única)        │
├─────────────────┬────────────────────┤
│  Modo A (WASM)  │  Modo B (servidor) │
│  WasmTransport  │  WebSocket / SSE   │
└─────────────────┴────────────────────┘
```

| | Modo A | Modo B |
|---|---|---|
| Onde Python roda | No browser (Pyodide) | No servidor (FastAPI) |
| Transporte | `pyodide.ffi` em-processo | WebSocket / SSE+POST |
| Latência de interação | Zero (sem rede) | Round-trip ao servidor |
| SEO / primeiro render | Limitado | Melhor (servidor pode pré-renderizar) |
| Estado compartilhado | Impossível entre abas | Possível (sessões no mesmo processo) |

!!! tip "Regra de ouro"
    Escolha o modo na CLI: `tempestweb dev --mode wasm` (estático) ou `tempestweb dev --mode server` (servidor) — ou na hora de implantar. O `app.py` nunca muda.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Estrutura esperada:

```
examples/
├── counter/
│   └── app.py          # make_state + view (o nosso app)
└── server-mode/
    └── serve.py        # entry-point do Modo B
```

---

## Passo 1 — O app do contador (inalterado)

Este é o `examples/counter/app.py`. Copie-o exatamente como está — ele roda em **ambos os modos** sem nenhuma modificação:

```python
"""Counter — the canonical tempestweb example.

This exact ``view`` runs unchanged in both modes:

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state.

    Returns:
        A fresh :class:`CounterState`.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

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

!!! info "Por que `Style(gap=8.0, padding=Edge.all(16))`?"
    `Style` e `Edge` são instâncias de `pydantic.BaseModel`. Quando o servidor serializa as patches para JSON, esses objetos precisam ser convertidos para dicts — é exatamente o que `_json_safe` faz (veja o Passo 5).

---

## Passo 2 — Criando o servidor com `create_app`

Crie `examples/server-mode/serve.py`:

```python
"""Mode B server entry-point — the counter example running on the server.

This module demonstrates how the *exact same* ``view`` function that runs inside
the browser (Mode A / Pyodide) can be served from a FastAPI host over WebSocket
and SSE without any change to the application code.

Usage::

    # Start the server (development):
    python examples/server-mode/serve.py

    # Then open the thin JS client in your browser at http://127.0.0.1:8000.
    # WebSocket endpoint: ws://127.0.0.1:8000/ws
    # SSE endpoints:      GET  http://127.0.0.1:8000/sse?session=<id>
    #                     POST http://127.0.0.1:8000/sse/<id>

The ``app`` symbol is importable by uvicorn / ASGI runners::

    uvicorn examples.server_mode.serve:app
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Module-level ASGI app — importable by any ASGI runner.
# ---------------------------------------------------------------------------

app: FastAPI = create_app(
    make_state,
    view,
    title="tempestweb — Mode B counter demo",
)


def run() -> None:
    """Launch the Mode B demo server programmatically.

    Binds to ``127.0.0.1:8000`` (internal-only; change to ``0.0.0.0`` when a
    separate origin needs to reach this host).
    """
    uvicorn.run(
        "examples.server_mode.serve:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
```

Isso é tudo. Duas linhas importantes:

```python hl_lines="2 3"
app: FastAPI = create_app(
    make_state,   # (1) factory de estado — chamada uma vez por conexão
    view,         # (2) a função de view — a mesma do Modo A
    title="tempestweb — Mode B counter demo",
)
```

---

## Passo 3 — O que `create_app` faz por dentro

`create_app` é uma fábrica que monta um `FastAPI` com três rotas:

| Rota | Protocolo | Direção | Finalidade |
|---|---|---|---|
| `GET /ws` | WebSocket | bidirecional | Transporte principal (B1) |
| `GET /sse?session=<id>` | SSE | servidor→cliente | Stream de patches (B5) |
| `POST /sse/{session_id}` | HTTP | cliente→servidor | Envio de eventos no SSE |

Cada conexão WebSocket recebe sua própria `AppSession` — o estado é completamente isolado entre clientes:

```
Conexão A                    Conexão B
   │                             │
   ├── AppSession(state_factory) ├── AppSession(state_factory)
   │       CounterState(value=0) │       CounterState(value=0)
   │                             │
   │   clicar "+": value=1       │   valor ainda 0
   │                             │
```

!!! check "Isolamento garantido"
    `state_factory` é chamada **por conexão**, nunca uma vez só. Dois usuários abrindo o app ao mesmo tempo começam com contadores independentes.

---

## Passo 4 — O wire format (formato de fio)

Toda comunicação entre Python e o cliente JS usa **envelopes JSON** com um campo `kind`:

```json
// Servidor → cliente: batch de patches após um clique
{
  "kind": "patches",
  "data": [
    {
      "path": ["children", 0],
      "set_props": { "content": "Count: 1" },
      "unset_props": []
    }
  ]
}
```

```json
// Cliente → servidor: evento de clique no botão "+"
{
  "kind": "event",
  "data": { "type": "click", "key": "inc" }
}
```

!!! note "O cliente JS é o mesmo nos dois modos"
    O cliente em `client/` nunca sabe se Python está no browser ou no servidor. Ele só envia eventos e aplica patches ao DOM — o transporte é transparente para ele.

---

## Passo 5 — O bug corrigido: `_json_safe` e objetos Pydantic

### Qual era o problema

O `view` do contador usa `Style` e `Edge` — ambos são instâncias de `pydantic.BaseModel`. Quando o servidor tentava serializar as patches iniciais para JSON, esses objetos não eram reconhecidos como serializáveis e causavam erro:

```
TypeError: Object of type Style is not JSON serializable
```

### A correção em `tempestweb/runtime/serialize.py`

A função `_json_safe` foi corrigida para tratar `BaseModel` antes do fallback genérico:

```python
from pydantic import BaseModel

def _json_safe(value: Any) -> Any:
    """Replace non-JSON-able prop values (handlers, Pydantic models) recursively.

    The IR carries live handler callables in ``props``; this strips them to
    ``None`` so the result is JSON-serializable.  Pydantic
    :class:`~pydantic.BaseModel` instances (e.g.
    :class:`~tempest_core.style.Style`,
    :class:`~tempest_core.style.Edge`) are lowered via
    ``model_dump(mode="json")`` which resolves colors, edges, enums and other
    structured style values to plain JSON-safe scalars before the recursive walk.

    Args:
        value: Any prop value drawn from a node's ``props``.

    Returns:
        A JSON-able value: callables become ``None``; Pydantic models are dumped
        to dicts; dicts and lists are walked recursively; everything else is
        returned unchanged.
    """
    if callable(value):
        return None
    if isinstance(value, BaseModel):          # ← correção: antes ausente
        return _json_safe(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
```

!!! warning "Ordem importa"
    O check `isinstance(value, BaseModel)` precisa vir **depois** do check `callable` e **antes** do check `dict` — porque `model_dump(mode="json")` retorna um `dict`, que depois é recursivamente processado pelo branch seguinte.

### Por que `mode="json"`?

`model_dump()` sem `mode="json"` pode retornar tipos Python que ainda não são serializáveis (ex.: `Enum`, `Color` com campos inteiros internos). `mode="json"` garante que tudo saia como scalars primitivos.

---

## Passo 6 — Rodando o servidor

### Desenvolvimento rápido via CLI

```bash
# Modo A — Python no browser (Pyodide / WASM)
tempestweb dev --mode wasm --path examples/counter

# Modo B — Python no servidor (FastAPI + WebSocket)
tempestweb dev --mode server --path examples/counter
```

!!! tip "Mesmo comando, modo diferente"
    Alterne entre `--mode wasm` e `--mode server` para ver o mesmo app rodando nas duas arquiteturas. A URL do browser e a UI são idênticas.

### Servidor direto com `serve.py`

```bash
python examples/server-mode/serve.py
```

Isso chama `uvicorn.run` programaticamente — sem subprocess, sem `os.system`. O servidor sobe em `http://127.0.0.1:8000`.

### Via uvicorn diretamente

```bash
uvicorn "examples.server_mode.serve:app" --host 127.0.0.1 --port 8000
```

!!! note "Por que `127.0.0.1` e não `0.0.0.0`?"
    Serviços internos usam `127.0.0.1` por padrão. Mude para `0.0.0.0` apenas quando um cliente de origem diferente (ex.: um servidor de desenvolvimento de frontend) precisar alcançar este host.

---

## Passo 7 — Testando com `TestClient`

O `fastapi.testclient.TestClient` do Starlette permite testar o servidor WebSocket **em-processo**, sem abrir portas de rede. Os testes são determinísticos e rodam no mesmo loop do `pytest`.

```python
"""Mode B end-to-end — the counter example served over WebSocket.

This test suite proves that the *exact same* ``make_state``/``view`` from
``examples/counter/app.py`` works unchanged when mounted on a FastAPI server
(Mode B).  It mirrors :mod:`tests.unit.test_server_ws` but uses the real
counter module instead of a local re-definition, demonstrating the "one view,
both modes" property of tempestweb.

The Starlette :class:`~fastapi.testclient.TestClient` drives the WebSocket
transport in-process, so no network port is opened and the suite is fully
deterministic.

Tests
-----
- :func:`test_initial_mount_receives_counter_zero` — the very first envelope
  after connecting contains the initial label ``"Count: 0"``.
- :func:`test_click_increments_counter` — sending a ``click`` event on key
  ``"inc"`` yields an Update patch that sets the label to ``"Count: 1"``.
- :func:`test_multiple_clicks_accumulate` — two successive clicks bring the
  label to ``"Count: 2"`` (stateful accumulation, not reset).
- :func:`test_decrement_via_dec_button` — clicking ``"dec"`` after three
  increments rolls the counter back to ``"Count: 2"``.
- :func:`test_two_connections_independent_state` — two simultaneous WebSocket
  connections own their own state; clicks on one do not leak to the other.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from examples.counter.app import make_state, view
from tempestweb.server import create_app

# ---------------------------------------------------------------------------
# Helpers (no dependencies — pure dict traversal)
# ---------------------------------------------------------------------------


def _find_label_content(node: dict[str, Any]) -> str | None:
    """Recursively find the ``label`` node's ``content`` prop in a wire tree.

    Args:
        node: A wire-format IR node (``{type, key, props, children}``).

    Returns:
        The ``content`` string if found, otherwise ``None``.
    """
    if node.get("key") == "label":
        content: Any = node["props"].get("content")
        return str(content) if content is not None else None
    for child in node.get("children", []):
        found = _find_label_content(child)
        if found is not None:
            return found
    return None


def _label_update(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the Update patch whose ``set_props`` contains ``content``.

    The reconciler may emit additional patches (e.g. re-serialised handler
    props) alongside the label update.  This isolates the one we care about.

    Args:
        patches: The ``data`` list from a ``patches`` envelope.

    Returns:
        The first Update patch that carries a ``content`` key in ``set_props``.

    Raises:
        AssertionError: If no such patch is present.
    """
    for patch in patches:
        if "content" in patch.get("set_props", {}):
            return patch
    raise AssertionError(f"no label content update in {patches}")


# ---------------------------------------------------------------------------
# Fixtures / app instance
# ---------------------------------------------------------------------------
# Each test creates its own TestClient so sessions do not bleed across tests.


def _client() -> TestClient:
    """Build a fresh TestClient wrapping a Mode B counter app.

    Returns:
        A configured :class:`~fastapi.testclient.TestClient`.
    """
    return TestClient(create_app(make_state, view, title="test-counter"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_mount_receives_counter_zero() -> None:
    """Connecting receives one ``patches`` envelope with the initial counter label."""
    with _client().websocket_connect("/ws") as ws:
        initial = ws.receive_json()

    assert initial["kind"] == "patches", f"unexpected kind: {initial['kind']}"
    root = initial["data"][0]
    assert root["path"] == [], "initial patch must target the root (empty path)"
    assert _find_label_content(root["node"]) == "Count: 0"


def test_click_increments_counter() -> None:
    """A single ``click`` on ``"inc"`` drives the counter from 0 → 1."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})

        update = ws.receive_json()

    assert update["kind"] == "patches"
    patch = _label_update(update["data"])
    assert patch["set_props"] == {"content": "Count: 1"}
    # The path is non-empty because it is an Update, not a full Replace.
    assert patch["path"] != []


def test_multiple_clicks_accumulate() -> None:
    """Two successive increments accumulate: 0 → 1 → 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        first = ws.receive_json()

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        second = ws.receive_json()

    assert _label_update(first["data"])["set_props"] == {"content": "Count: 1"}
    assert _label_update(second["data"])["set_props"] == {"content": "Count: 2"}


def test_decrement_via_dec_button() -> None:
    """Clicking ``"dec"`` after three increments rolls the counter back to 2."""
    with _client().websocket_connect("/ws") as ws:
        ws.receive_json()  # discard initial mount

        for _ in range(3):
            ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
            ws.receive_json()  # consume each update

        ws.send_json({"kind": "event", "data": {"type": "click", "key": "dec"}})
        update = ws.receive_json()

    assert _label_update(update["data"])["set_props"] == {"content": "Count: 2"}


def test_two_connections_independent_state() -> None:
    """Two simultaneous WebSocket connections own fully isolated state.

    Connection A is clicked twice; connection B is never clicked and then
    clicked once.  B must yield ``Count: 1``, not ``Count: 3``.
    """
    client = _client()
    with (
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        # Drive A up to 2.
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        ws_a.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_a1 = ws_a.receive_json()
        update_a2 = ws_a.receive_json()
        assert _label_update(update_a1["data"])["set_props"] == {"content": "Count: 1"}
        assert _label_update(update_a2["data"])["set_props"] == {"content": "Count: 2"}

        # B was never touched: its first click must yield Count: 1, not Count: 3.
        ws_b.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        update_b = ws_b.receive_json()
        assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}
```

### Explicando cada teste

#### `test_initial_mount_receives_counter_zero`

```python
with _client().websocket_connect("/ws") as ws:
    initial = ws.receive_json()

assert initial["kind"] == "patches"
root = initial["data"][0]
assert root["path"] == []                           # patch raiz (Replace)
assert _find_label_content(root["node"]) == "Count: 0"
```

Ao conectar, o servidor envia imediatamente um envelope `patches` com um patch do tipo `Replace` no caminho raiz (`path == []`). Esse patch contém a árvore inteira de widgets. Inspecionamos recursivamente até achar o nó com `key="label"` e verificamos que o `content` é `"Count: 0"`.

#### `test_click_increments_counter`

```python
ws.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
update = ws.receive_json()

patch = _label_update(update["data"])
assert patch["set_props"] == {"content": "Count: 1"}
assert patch["path"] != []   # Update, não Replace — caminho não é vazio
```

O cliente envia um evento de clique. O servidor resolve o handler `increment`, chama `set_state`, o reconciliador calcula o diff e emite um patch do tipo `Update` com apenas `{"content": "Count: 1"}` em `set_props` — só o que mudou.

!!! tip "Update vs. Replace"
    Um `Replace` (caminho `[]`) remonta toda a árvore. Um `Update` (caminho não vazio) toca apenas as props que mudaram naquele nó. O reconciliador escolhe o mínimo necessário — por isso clicar em `+` gera apenas um `Update` no nó do texto, não um `Replace` de tudo.

#### `test_multiple_clicks_accumulate`

Dois cliques sucessivos na mesma conexão produzem `"Count: 1"` e `"Count: 2"`. Isso confirma que o estado **acumula** — cada `AppSession` guarda o estado entre eventos.

#### `test_decrement_via_dec_button`

Três incrementos seguidos de um decremento devem produzir `"Count: 2"`. Isso verifica tanto o botão `dec` quanto a corretude do estado acumulado.

#### `test_two_connections_independent_state`

```python
client = _client()
with (
    client.websocket_connect("/ws") as ws_a,
    client.websocket_connect("/ws") as ws_b,
):
    ...
    # B nunca foi clicado; seu primeiro clique deve dar Count: 1, não Count: 3
    assert _label_update(update_b["data"])["set_props"] == {"content": "Count: 1"}
```

Este é o teste mais importante: dois clientes simultâneos no **mesmo** servidor têm estados completamente isolados. Clicar em `ws_a` não afeta `ws_b`.

---

## Verificação automatizada ✅

Rode os checks completos:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes (inclui os 5 testes deste tutorial)
pytest -q
```

!!! check "Resultado esperado"
    ```
    tests/unit/test_example_server_mode.py .....   5 passed
    ```
    Todos os 5 testes verdes — montagem inicial, clique simples, acúmulo, decremento e isolamento entre conexões.

---

## Como funciona por dentro

### O ciclo completo Modo B

```
Browser                       Servidor Python
   │                               │
   │──── WS connect ──────────────▶│
   │                               │  AppSession criada
   │                               │  state_factory() → CounterState(value=0)
   │                               │  view(app) → Widget tree
   │                               │  reconciliador → patch inicial
   │◀─── {"kind":"patches"} ───────│
   │                               │
   │  usuário clica "+"            │
   │──── {"kind":"event",          │
   │      "data":{"type":"click",  │
   │              "key":"inc"}} ──▶│
   │                               │  resolve_handler("inc", "click")
   │                               │  → increment()
   │                               │  app.set_state(...)
   │                               │  view(app) → nova árvore
   │                               │  diff → Update patch
   │◀─── {"kind":"patches"} ───────│
   │  DOM atualizado               │
```

### `AppSession` — a sessão por conexão

`AppSession` é o coração do Modo B. Ela:

1. Constrói um `App` isolado com `state_factory()` e `view`
2. Envia as patches iniciais via `transport.send_patches`
3. Loop: recebe evento → `dispatch` → resolve handler → `set_state` → patches de volta
4. Ao desconectar, cancela todas as tasks de envio pendentes (concorrência estruturada)

### `WebSocketTransport` — o canal

`WebSocketTransport` é um `PatchTransport` concreto. Ele roda um **demux** interno (task asyncio) que lê envelopes do socket e os roteia:

- `kind == "event"` → fila interna (consumida por `recv_event`)
- `kind == "native_result"` → handler registrado (para proxying de APIs nativas)

Isso mantém o loop da sessão limpo: ele só vê eventos de usuário, nunca envelopes de protocolo.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ A diferença entre Modo A (WASM) e Modo B (servidor) — e que o `view` é idêntico nos dois
- ✅ Usar `create_app(make_state, view)` para empacotar qualquer app em um servidor FastAPI
- ✅ Que `state_factory` é chamada **por conexão**, garantindo isolamento total entre clientes
- ✅ O formato dos envelopes JSON (`kind: patches / event`) que trafegam pelo WebSocket
- ✅ Como testar o servidor com `TestClient` sem abrir portas de rede
- ✅ Por que `_json_safe` precisa tratar `pydantic.BaseModel` antes de serializar para JSON
- ✅ A diferença entre um patch `Replace` (montagem inicial, caminho `[]`) e um `Update` (diff, caminho não vazio)

---

## Próximos passos

- 💡 Explore o [transporte SSE](../tutorial/modes.md) — a alternativa sem WebSocket para ambientes com proxies HTTP
- 💡 Adicione [WebPush](../pwa.md) para notificações push no Modo B
- 💡 Leia `docs/contract.md` para o formato completo de todos os 5 tipos de patch
- 💡 Veja `tests/unit/test_server_ws.py` para testes de nível mais baixo do transporte WebSocket isolado
