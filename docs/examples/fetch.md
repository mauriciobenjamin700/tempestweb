# Fetch assíncrono — `idle → loading → loaded/error` ⏳

**Modos: A/B** — usa widgets do core e um handler `async` (a fonte é injetada).

O padrão canônico de I/O assíncrono no tempestweb: apertar **Load** dispara um
handler `async` que marca a fase como `loading` (mostrando um `Spinner`), aguarda
uma busca I/O-bound e re-renderiza com o resultado. Sem travar a UI. 🚀

!!! note "A fonte é injetada"
    O callable `fetch` é um **campo do estado** com um default. Isso deixa o
    exemplo determinístico nos testes (injeta-se uma coroutine fake); num app real
    você passaria `native.http.request`. A `view` nunca bloqueia o event loop.

---

## O que este exemplo mostra

- **Handler `async`** — `load()` faz `await` de uma fonte injetada sem congelar a UI.
- **Máquina de fases** — um `StrEnum` `Phase` (`idle`/`loading`/`loaded`/`error`)
  dirige o que a `view` renderiza.
- **`Spinner`** enquanto carrega; **`LazyColumn`** com as linhas ao carregar.
- **Tratamento de erro** — qualquer exceção do `await` transiciona para `error`.

---

## Rodando ▶

```bash
tempestweb dev --mode wasm     --path examples/fetch   # Python no browser (Pyodide)
tempestweb dev --mode server   --path examples/fetch   # Python no servidor (FastAPI + WS)
```

---

## O código

```python
"""Async fetch view — exercises an ``async`` handler driving the UI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    LazyColumn,
    Spinner,
    Text,
)

#: A coroutine that resolves to the fetched rows. Injected into the view so the
#: example stays deterministic under test; in a real app this wraps
#: ``native.http.request``.
Fetcher = Callable[[], Awaitable[list[str]]]


class Phase(StrEnum):
    """The lifecycle phase of the async fetch.

    Attributes:
        IDLE: Nothing has been requested yet.
        LOADING: A fetch is in flight (the spinner is shown).
        LOADED: The fetch resolved and rows are available.
        ERROR: The fetch raised; an error message is shown.
    """

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


async def _default_fetch() -> list[str]:
    """Return a fixed list of rows, standing in for a network call.

    Returns:
        A small list of sample rows.
    """
    return ["alpha", "beta", "gamma"]


@dataclass
class FetchState:
    """State for the async fetch app.

    Attributes:
        phase: The current lifecycle phase.
        rows: The rows fetched on success.
        error: The error message shown on failure.
        fetch: The injected coroutine that performs the fetch.
    """

    phase: Phase = Phase.IDLE
    rows: list[str] = field(default_factory=list)
    error: str = ""
    fetch: Fetcher = _default_fetch


def make_state() -> FetchState:
    """Build the initial, idle fetch state.

    Returns:
        A fresh :class:`FetchState`.
    """
    return FetchState()


def view(app: App[FetchState]) -> Widget:
    """Render the fetch UI from the current lifecycle phase.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def load() -> None:
        app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
        try:
            rows = await app.state.fetch()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            # Bind the message before the except block clears ``exc`` so the
            # closure below captures a live value.
            message = str(exc)

            def on_error(s: FetchState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_success(s: FetchState) -> None:
            s.phase = Phase.LOADED
            s.rows = rows

        app.set_state(on_success)

    children: list[Widget] = [
        Text(content="Async fetch", key="title"),
        Button(label="Load", on_click=load, key="load"),
    ]

    if app.state.phase is Phase.LOADING:
        children.append(Spinner(key="spinner"))
    elif app.state.phase is Phase.ERROR:
        children.append(Text(content=f"Error: {app.state.error}", key="error"))
    elif app.state.phase is Phase.LOADED:
        rows = app.state.rows
        children.append(
            LazyColumn(
                item_count=len(rows),
                item_builder=lambda i: Text(content=rows[i]),
                key="rows",
            )
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=children,
    )
```

---

## Peça por peça

### `set_state` antes e depois do `await`

```python
async def load() -> None:
    app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))  # (1) re-render imediato
    rows = await app.state.fetch()                               # (2) I/O
    app.set_state(on_success)                                    # (3) re-render final
```

A chamada `set_state(LOADING)` acontece **antes** do `await` — então o `Spinner`
pinta na hora. Só depois o `await` resolve e a fase vira `loaded`. Entre os dois, a
UI nunca congela: o runtime aguarda o handler no event loop do browser (Modo A) ou
do servidor (Modo B).

### A fase dirige a árvore

```python
if app.state.phase is Phase.LOADING:
    children.append(Spinner(key="spinner"))
elif app.state.phase is Phase.ERROR:
    children.append(Text(content=f"Error: {app.state.error}", key="error"))
elif app.state.phase is Phase.LOADED:
    children.append(LazyColumn(...))
```

Construir uma lista `children` e ir dando `append` conforme a fase é um padrão
idiomático para renderização condicional.

!!! warning "Capture a mensagem antes de sair do `except`"
    ```python
    except Exception as exc:
        message = str(exc)   # ← capture aqui
        def on_error(s): s.error = message
    ```
    Em Python, `exc` é apagado ao fim do bloco `except`. Ligar `message` antes
    garante que a closure `on_error` capture um valor vivo.

---

## Recapitulando

Neste exemplo você viu:

- ✅ Um **handler `async`** que faz `await` sem travar a UI
- ✅ A máquina de fases **`idle → loading → loaded/error`** dirigindo a `view`
- ✅ **`set_state` antes e depois do `await`** para pintar o `loading` na hora
- ✅ Uma **fonte injetada** que torna o exemplo determinístico nos testes
- ✅ O padrão rodando inalterado nos **Modos A/B**

---

## Próximos passos

- 💡 O [Clima (HTTP + geolocalização)](weather-native.md) encadeia **duas** capacidades nativas com esse mesmo padrão
- 💡 Volte à [Lista de tarefas](todo.md) para outro uso de `LazyColumn`
- 💡 Leia [capacidades nativas](../capabilities.md) para trocar `_default_fetch` por `native.http.request`
