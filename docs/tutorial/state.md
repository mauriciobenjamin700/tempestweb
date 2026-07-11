# 2. Estado e handlers

Na [página anterior](view.md) desenhamos a árvore. Agora vamos fazer os botões
**mudarem o estado** — e ver como o tempestweb transforma essa mudança em uma nova
árvore automaticamente.

## O estado é um dataclass

O counter guarda um único inteiro:

```python
from dataclasses import dataclass


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()
```

`make_state()` é a fábrica do estado inicial. O runtime chama isso uma vez ao
montar o app.

!!! note "Por que uma fábrica?"
    No Modo B (servidor), **cada conexão tem seu próprio estado**, isolado. A
    fábrica garante que cada sessão começa com um `CounterState` fresco, sem
    compartilhar referências entre clientes.

## Handlers mudam o estado via `set_state`

Um handler **nunca** muta `app.state` diretamente. Ele chama `app.set_state`,
passando uma função que aplica a mudança:

```python
def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:  # (1)!
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                children=[
                    Button(label="-", on_click=decrement, key="dec"),  # (2)!
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

1. O handler é uma função normal (ou `async def`). Ele descreve a **transição de
   estado**, não toca no DOM.
2. `on_click=increment` liga o evento de clique ao handler. A `key="inc"` é o que
   o evento carrega de volta para o Python resolver o handler.

!!! warning "Nunca mute o DOM no handler"
    Você não escreve `document.getElementById(...)`. Você muda o **estado**; o
    reconciliador descobre o diff e o cliente aplica os patches. Essa é a regra
    de ouro — vale igualzinho nos três modos.

## O ciclo: evento → estado → rebuild → patches

Quando o usuário clica no `+`:

```text
1. Cliente captura o clique no Button key="inc"
2. Cliente envia o evento → { "type": "click", "key": "inc", "payload": {} }
3. Python resolve key="inc" → handler increment
4. increment chama app.set_state → value passa de 0 para 1
5. O runtime roda view() de novo → nova árvore
6. diff(árvore antiga, árvore nova) → [ Update no Text "label" ]
7. Cliente aplica o patch → o texto vira "Count: 1"
```

!!! info "Coalescência"
    Se um handler chama `set_state` várias vezes no mesmo tick, o core **coalesce**
    tudo num único `diff`. O transporte recebe **uma lista de patches por tick** —
    o cliente aplica a lista inteira antes do próximo frame. Você nunca vê estados
    intermediários piscando.

## Handlers podem ser `async`

O runtime roda sobre um event loop asyncio, então handlers podem ser `async def`
— útil para buscar dados antes de atualizar o estado:

```python
async def load_total() -> None:
    """Fetch a total from a typed native HTTP wrapper, then update state."""
    total = await app.native.http.get_json("/api/total")  # awaitable tipado
    app.set_state(lambda s: setattr(s, "value", total["count"]))
```

!!! tip "Async-first absorve a latência do Modo B"
    No Modo B há um round-trip de rede por interação. A regra async-first
    (handler → estado → rebuild coalescido) absorve isso naturalmente — o mesmo
    código funciona local (Modo A) e remoto (Modo B).

## Recap

- O estado é um `dataclass`; `make_state()` cria o inicial (isolado por sessão).
- Handlers chamam `app.set_state(fn)` — **nunca** mutam o DOM.
- O ciclo é **evento → estado → rebuild → diff → patches**.
- Múltiplos `set_state` no mesmo tick **coalescem** num só diff.
- Handlers podem ser `async`.

Mas o que exatamente o `diff` emite? Vamos olhar os
[patches na rede](patches.md). 🚀
