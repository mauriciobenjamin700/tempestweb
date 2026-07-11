# Fila offline — escritas duráveis que sobrevivem a estar offline 📥

**Modos: A/B** — usa componentes e o formato Python de evento (`event.value`).

Um pequeno "log de atividade": digitar uma nota e apertar **Queue** enfileira uma
mutação na **fila offline durável** (`native.offline.enqueue`) em vez de bater na
rede direto — então funciona **sem conectividade**. O **Replay** drena a fila em
ordem FIFO. 🚀

!!! note "Por que uma fila em vez de um POST direto?"
    Num app real, um `POST /api/log` falha quando o usuário está sem rede. Com a
    `native.offline`, a escrita é **persistida localmente** e reenviada mais tarde
    — o runtime também drena a fila **automaticamente** quando a conectividade
    volta. O servidor deduplica pela chave de idempotência, então um replay nunca
    aplica a mesma mutação duas vezes.

---

## O que este exemplo mostra

- **`native.offline.enqueue(method, url, body)`** — persiste uma mutação na fila
  durável em vez de fazer a requisição de rede na hora.
- **`native.offline.size()`** — devolve quantas mutações estão pendentes.
- **`native.offline.replay()`** — drena a fila e devolve um `ReplayResult` com
  `sent` (enviadas) e `remaining` (restantes).
- **Render inicial sem bridge** — o primeiro mount só *lê* o estado, então
  `build(view(app))` fica verde sem nenhum bridge nativo instalado; os handlers
  `async` é que chamam a capacidade.

---

## Rodando ▶

```bash
tempestweb run --mode wasm     --path examples/offline-queue   # Python no browser (Pyodide)
tempestweb run --mode server   --path examples/offline-queue   # Python no servidor (FastAPI + WS)
```

O **mesmo** `view` roda inalterado nos dois modos — ele lê `event.value` do
`TextChangeEvent` (o formato de evento Python).

---

## O código

```python
"""Offline queue — durable writes that survive being offline (native.offline)."""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent
from tempestweb import native


@dataclass
class QueueState:
    """State for the offline-queue demo.

    Attributes:
        draft: The text currently typed into the input.
        queued: The number of pending mutations (from the last refresh).
        status: A short human-readable status line.
        log: The notes queued so far, in order.
    """

    draft: str = ""
    queued: int = 0
    status: str = ""
    log: list[str] = field(default_factory=list)


def make_state() -> QueueState:
    """Build the initial state.

    Returns:
        A fresh :class:`QueueState`.
    """
    return QueueState()


def view(app: App[QueueState]) -> Widget:
    """Render the input, the pending count, and the replay control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_draft(event: TextChangeEvent) -> None:
        value = event.value
        app.set_state(lambda s: setattr(s, "draft", value))

    async def queue_note() -> None:
        text = app.state.draft
        await native.offline.enqueue("POST", "/api/log", {"text": text})
        size = await native.offline.size()

        def _update(s: QueueState) -> None:
            s.queued = size
            s.draft = ""
            s.log = [*s.log, text]
            s.status = f"queued: {text}"

        app.set_state(_update)

    async def replay() -> None:
        result = await native.offline.replay()

        def _update(s: QueueState) -> None:
            s.queued = result.remaining
            s.status = f"replayed {result.sent}, {result.remaining} left"

        app.set_state(_update)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Pending: {app.state.queued}", key="pending"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Input(
                        value=app.state.draft,
                        placeholder="a note to sync",
                        on_change=on_draft,
                        key="draft",
                    ),
                    Button(label="Queue", on_click=queue_note, key="queue"),
                    Button(label="Replay", on_click=replay, key="replay"),
                ],
            ),
            Text(content=app.state.status, key="status"),
            Column(
                style=Style(gap=2.0),
                children=[
                    Text(content=f"• {entry}", key=f"log-{i}")
                    for i, entry in enumerate(app.state.log)
                ],
            ),
        ],
    )
```

---

## Peça por peça

### Enfileirar em vez de enviar

```python
async def queue_note() -> None:
    text = app.state.draft
    await native.offline.enqueue("POST", "/api/log", {"text": text})
    size = await native.offline.size()
    ...
```

`queue_note` é um handler `async`. Ele **não** faz o POST — ele *enfileira* a
mutação (`method`, `url`, `body`) e depois consulta o tamanho da fila. Como a
escrita é durável, ela sobrevive a um refresh da página ou a ficar offline.

### Drenar a fila

```python
async def replay() -> None:
    result = await native.offline.replay()
    # result.sent → enviadas ; result.remaining → restantes
```

`replay()` tenta enviar tudo em ordem FIFO e devolve um `ReplayResult`. Em
produção o runtime chama isso sozinho quando a conectividade volta — o botão só
torna o fluxo explícito e testável.

!!! tip "O mount inicial é livre de bridge"
    O primeiro render só lê `app.state` — nenhuma chamada nativa. Por isso
    `build(view(app))` funciona **sem bridge instalado**, e os testes dirigem os
    handlers `async` por um bridge com script.

!!! info "Idempotência no servidor"
    Cada mutação carrega uma chave de idempotência. Se um replay reenviar algo que
    o servidor já processou, ele deduplica — então reconexões instáveis nunca
    aplicam a mesma escrita duas vezes.

---

## Recapitulando

Neste exemplo você viu:

- ✅ **`native.offline.enqueue`** para tornar escritas duráveis e tolerantes a offline
- ✅ **`native.offline.size`** para expor a contagem de pendentes
- ✅ **`native.offline.replay`** devolvendo `ReplayResult(sent, remaining)`
- ✅ Um mount inicial **livre de bridge** com handlers `async` que chamam a capacidade
- ✅ O padrão rodando inalterado nos **Modos A/B**

---

## Próximos passos

- 💡 Veja [PWA e offline](../pwa.md) para a história completa de offline + WebPush
- 💡 O [Tour do Modo C](transpile-tour.md) também usa `native.offline` num bundle estático
- 💡 Leia [capacidades nativas](../capabilities.md) para o módulo `tempestweb.native` inteiro
