# Stopwatch — Cronômetro com Voltas 🚀

Construa um cronômetro funcional com botões de Start/Stop, Lap e Reset — e aprenda a gerenciar estado temporal **de forma determinística** no tempestweb.

---

## O que você vai construir

Um cronômetro clássico com:

- ⏱ Display grande mostrando `MM:SS.T`
- ▶ Botão **Start/Stop** que alterna em tempo real
- 🏁 Botão **Lap** para registrar tempos de volta
- 🔄 Botão **Reset** que zera tudo
- 🔬 Botão **Tick (+0.1 s)** para avançar o relógio manualmente (ideal para testes)

!!! note "Nota — tempo determinístico"
    O tempo é armazenado como um **inteiro de décimos de segundo** (`tenths: int`). Isso torna a árvore de widgets completamente determinística — sem `datetime.now()` nem `time.time()` dentro de `view()`. Em produção, o runtime chama `app.set_state` a partir de um loop `asyncio.sleep(0.1)`; a função `view` nunca precisa mudar.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leia antes (opcional, mas recomendado):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/stopwatch
touch examples/stopwatch/app.py
```

---

## Passo 1 — Definindo o estado

Todo app tempestweb começa pelo **estado**. Pense primeiro no que precisa ser lembrado entre os renders.

Para um cronômetro, precisamos de três coisas:

| Campo | Tipo | Significado |
|---|---|---|
| `running` | `bool` | Está contando agora? |
| `tenths` | `int` | Décimos de segundo acumulados |
| `laps` | `list[int]` | Tempos de volta registrados |

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StopwatchState:
    """Mutable state for the stopwatch application.

    Attributes:
        running: Whether the stopwatch is currently ticking.
        tenths: Total elapsed time in tenths of a second (0.1 s per unit).
        laps: Recorded lap times, each expressed as tenths of a second.
    """

    running: bool = False
    tenths: int = 0
    laps: list[int] = field(default_factory=list)


def make_state() -> StopwatchState:
    """Build the initial stopwatch state.

    Returns:
        A fresh :class:`StopwatchState` with the clock at zero.
    """
    return StopwatchState()
```

!!! tip "Dica — `field(default_factory=list)`"
    Nunca use `laps: list[int] = []` em um dataclass. Python compartilharia a mesma lista entre todas as instâncias. `field(default_factory=list)` garante uma lista nova a cada instância.

---

## Passo 2 — Formatando o tempo

Antes da UI, precisamos de um helper que converte décimos de segundo em algo legível:

```python
def _format_time(tenths: int) -> str:
    """Format a tenths-of-a-second count as ``MM:SS.T``.

    Args:
        tenths: Elapsed time expressed in tenths of a second.

    Returns:
        A human-readable string of the form ``MM:SS.T``, e.g. ``01:23.7``.
    """
    total_seconds: int = tenths // 10
    t_digit: int = tenths % 10
    minutes: int = total_seconds // 60
    seconds: int = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}.{t_digit}"
```

Exemplos rápidos:

| `tenths` | Resultado |
|---|---|
| `0` | `00:00.0` |
| `7` | `00:00.7` |
| `137` | `00:13.7` |
| `3600` | `06:00.0` |

---

## Passo 3 — Os handlers de evento

Dentro de `view()`, definimos as funções que respondem aos cliques dos botões. Cada uma chama `app.set_state(mutador)` onde o mutador recebe o estado atual e o modifica no lugar:

```python
def start_stop() -> None:
    """Toggle the running flag on/off."""
    app.set_state(lambda s: setattr(s, "running", not s.running))

def record_lap() -> None:
    """Append the current elapsed time to the lap list."""

    def _mutate(s: StopwatchState) -> None:
        s.laps.append(s.tenths)

    app.set_state(_mutate)

def reset() -> None:
    """Stop the clock and clear all state."""

    def _mutate(s: StopwatchState) -> None:
        s.running = False
        s.tenths = 0
        s.laps = []

    app.set_state(_mutate)

def tick() -> None:
    """Advance the clock by one tenth of a second (0.1 s).

    In a real deployment the runtime drives this from a timer; here it is
    exposed as a button so the example stays framework-agnostic and fully
    testable without async scheduling.  The handler is a no-op when the
    stopwatch is not running, matching the behaviour of a real timer that
    would simply not fire.
    """

    def _mutate(s: StopwatchState) -> None:
        if s.running:
            s.tenths += 1

    app.set_state(_mutate)
```

!!! info "Nota — por que `tick` é um botão?"
    Em produção, `tick` seria disparado por um loop `asyncio.sleep(0.1)` no servidor (Modo B) ou por um `setInterval` no Service Worker (Modo A). Expô-lo como botão mantém o exemplo completamente **auto-contido e testável** sem um timer real rodando em background.

---

## Passo 4 — Construindo a árvore de widgets

Agora montamos a UI. O cronômetro tem três seções:

1. **Display** — número grande em `monospace`, verde quando rodando
2. **Controles** — quatro botões em `Row`
3. **Lista de voltas** — aparece só quando há voltas registradas

```python
from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)


def view(app: App[StopwatchState]) -> Widget:
    """Render the stopwatch UI from the current state."""
    state: StopwatchState = app.state

    # ... (handlers definidos aqui — ver Passo 3)

    start_stop_label: str = "Stop" if state.running else "Start"
    main_display: str = _format_time(state.tenths)

    lap_widgets: list[Widget] = [
        Row(
            key=f"lap-{i}",
            style=Style(
                justify=JustifyContent.SPACE_BETWEEN,
                padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
                border=None,
            ),
            children=[
                Text(
                    content=f"Lap {i + 1}",
                    key=f"lap-label-{i}",
                    style=Style(
                        color=Color(r=100, g=100, b=100),
                        font_size=14.0,
                    ),
                ),
                Text(
                    content=_format_time(t),
                    key=f"lap-time-{i}",
                    style=Style(font_size=14.0, font_weight=FontWeight.MEDIUM),
                ),
            ],
        )
        for i, t in enumerate(state.laps)
    ]

    return Column(
        style=Style(
            gap=24.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Stopwatch",
                key="title",
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content=main_display,
                key="display",
                style=Style(
                    font_size=56.0,
                    font_weight=FontWeight.BOLD,
                    font_family="monospace",
                    text_align=TextAlign.CENTER,
                    color=(
                        Color(r=34, g=139, b=34)
                        if state.running
                        else Color(r=30, g=30, b=30)
                    ),
                    letter_spacing=2.0,
                ),
            ),
            Row(
                key="controls",
                style=Style(
                    gap=12.0,
                    justify=JustifyContent.CENTER,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Button(
                        label=start_stop_label,
                        on_click=start_stop,
                        key="start-stop",
                    ),
                    Button(
                        label="Lap",
                        on_click=record_lap,
                        key="lap",
                    ),
                    Button(
                        label="Reset",
                        on_click=reset,
                        key="reset",
                    ),
                ],
            ),
            Row(
                key="tick-row",
                style=Style(justify=JustifyContent.CENTER),
                children=[
                    Button(
                        label="Tick (+0.1 s)",
                        on_click=tick,
                        key="tick",
                    ),
                ],
            ),
            *(
                [
                    Column(
                        key="lap-list",
                        style=Style(
                            gap=4.0,
                            padding=Edge.all(8.0),
                        ),
                        children=[
                            Text(
                                content="Laps",
                                key="laps-header",
                                style=Style(
                                    font_size=16.0,
                                    font_weight=FontWeight.SEMIBOLD,
                                ),
                            ),
                            *lap_widgets,
                        ],
                    )
                ]
                if state.laps
                else []
            ),
        ],
    )
```

!!! tip "Dica — renderização condicional com `*([] if ... else [...])`"
    O Python não tem JSX, mas o padrão `*([widget] if condição else [])` dentro de uma lista de `children` funciona perfeitamente como renderização condicional. A lista de voltas só aparece no DOM quando `state.laps` não está vazia.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Stopwatch — demonstrates time & timer state management in tempestweb.

A classic stopwatch with start/stop/reset controls and a lap-time recorder.
The elapsed time is stored as accumulated integer tenths-of-a-second so the
widget tree is fully deterministic — no wall-clock access is needed inside
``view``.  A "Tick (+0.1 s)" button advances the clock by one tenth of a
second, making the example self-contained and easily testable without a real
timer source.  In a deployed app the runtime would wire up a recurring
``app.set_state`` call from a ``setTimeout`` / ``asyncio.sleep`` loop; the
widget tree itself never changes.

Both modes work unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class StopwatchState:
    """Mutable state for the stopwatch application.

    Attributes:
        running: Whether the stopwatch is currently ticking.
        tenths: Total elapsed time in tenths of a second (0.1 s per unit).
        laps: Recorded lap times, each expressed as tenths of a second.
    """

    running: bool = False
    tenths: int = 0
    laps: list[int] = field(default_factory=list)


def make_state() -> StopwatchState:
    """Build the initial stopwatch state.

    Returns:
        A fresh :class:`StopwatchState` with the clock at zero.
    """
    return StopwatchState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_time(tenths: int) -> str:
    """Format a tenths-of-a-second count as ``MM:SS.T``.

    Args:
        tenths: Elapsed time expressed in tenths of a second.

    Returns:
        A human-readable string of the form ``MM:SS.T``, e.g. ``01:23.7``.
    """
    total_seconds: int = tenths // 10
    t_digit: int = tenths % 10
    minutes: int = total_seconds // 60
    seconds: int = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}.{t_digit}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[StopwatchState]) -> Widget:
    """Render the stopwatch UI from the current state.

    The tree is a :class:`~tempest_core.widgets.Column` with three
    sections:

    1. **Display** — a large monospaced readout showing ``MM:SS.T``.
    2. **Controls** — Start/Stop, Lap, Reset and Tick buttons.
    3. **Lap list** — a scrollable column of recorded lap times.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: StopwatchState = app.state

    # -- Handlers --

    def start_stop() -> None:
        """Toggle the running flag on/off."""
        app.set_state(lambda s: setattr(s, "running", not s.running))

    def record_lap() -> None:
        """Append the current elapsed time to the lap list."""

        def _mutate(s: StopwatchState) -> None:
            s.laps.append(s.tenths)

        app.set_state(_mutate)

    def reset() -> None:
        """Stop the clock and clear all state."""

        def _mutate(s: StopwatchState) -> None:
            s.running = False
            s.tenths = 0
            s.laps = []

        app.set_state(_mutate)

    def tick() -> None:
        """Advance the clock by one tenth of a second (0.1 s).

        In a real deployment the runtime drives this from a timer; here it is
        exposed as a button so the example stays framework-agnostic and fully
        testable without async scheduling.  The handler is a no-op when the
        stopwatch is not running, matching the behaviour of a real timer that
        would simply not fire.
        """

        def _mutate(s: StopwatchState) -> None:
            if s.running:
                s.tenths += 1

        app.set_state(_mutate)

    # -- Derived display values --

    start_stop_label: str = "Stop" if state.running else "Start"
    main_display: str = _format_time(state.tenths)

    # -- Lap rows --

    lap_widgets: list[Widget] = [
        Row(
            key=f"lap-{i}",
            style=Style(
                justify=JustifyContent.SPACE_BETWEEN,
                padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
                border=None,
            ),
            children=[
                Text(
                    content=f"Lap {i + 1}",
                    key=f"lap-label-{i}",
                    style=Style(
                        color=Color(r=100, g=100, b=100),
                        font_size=14.0,
                    ),
                ),
                Text(
                    content=_format_time(t),
                    key=f"lap-time-{i}",
                    style=Style(font_size=14.0, font_weight=FontWeight.MEDIUM),
                ),
            ],
        )
        for i, t in enumerate(state.laps)
    ]

    # -- Full tree --

    return Column(
        style=Style(
            gap=24.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            # Title
            Text(
                content="Stopwatch",
                key="title",
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Main time display
            Text(
                content=main_display,
                key="display",
                style=Style(
                    font_size=56.0,
                    font_weight=FontWeight.BOLD,
                    font_family="monospace",
                    text_align=TextAlign.CENTER,
                    color=(
                        Color(r=34, g=139, b=34)
                        if state.running
                        else Color(r=30, g=30, b=30)
                    ),
                    letter_spacing=2.0,
                ),
            ),
            # Control buttons
            Row(
                key="controls",
                style=Style(
                    gap=12.0,
                    justify=JustifyContent.CENTER,
                    align=AlignItems.CENTER,
                ),
                children=[
                    Button(
                        label=start_stop_label,
                        on_click=start_stop,
                        key="start-stop",
                    ),
                    Button(
                        label="Lap",
                        on_click=record_lap,
                        key="lap",
                    ),
                    Button(
                        label="Reset",
                        on_click=reset,
                        key="reset",
                    ),
                ],
            ),
            # Tick button (testing / demo handle)
            Row(
                key="tick-row",
                style=Style(justify=JustifyContent.CENTER),
                children=[
                    Button(
                        label="Tick (+0.1 s)",
                        on_click=tick,
                        key="tick",
                    ),
                ],
            ),
            # Lap list (only rendered when there are recorded laps)
            *(
                [
                    Column(
                        key="lap-list",
                        style=Style(
                            gap=4.0,
                            padding=Edge.all(8.0),
                        ),
                        children=[
                            Text(
                                content="Laps",
                                key="laps-header",
                                style=Style(
                                    font_size=16.0,
                                    font_weight=FontWeight.SEMIBOLD,
                                ),
                            ),
                            *lap_widgets,
                        ],
                    )
                ]
                if state.laps
                else []
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/stopwatch
```

O Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/stopwatch
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:
    
    1. Display `00:00.0` centralizado
    2. Quatro botões: **Start**, **Lap**, **Reset**, **Tick (+0.1 s)**
    3. Clique **Start** → label muda para **Stop** e display fica verde
    4. Clique **Tick (+0.1 s)** repetidamente → display avança
    5. Clique **Lap** → seção "Laps" aparece com o tempo atual
    6. Clique **Reset** → tudo zera e a seção de voltas desaparece

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

Todos devem passar em verde. O exemplo foi especificamente projetado para ser `mypy --strict` clean — toda variável e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização

```
Clique no botão
      │
      ▼
handler (ex: start_stop)
      │
      ▼
app.set_state(mutador)
      │
      ▼
tempestweb aplica o mutador → novo estado
      │
      ▼
view(app) chamada novamente → nova árvore de widgets
      │
      ▼
reconciliador calcula diff (patches)
      │
      ▼
DOM atualizado (mínimo de mudanças)
```

### Estado vs. valores derivados

O `state` guarda **apenas o mínimo** necessário (`running`, `tenths`, `laps`). Tudo o mais — `main_display`, `start_stop_label`, `lap_widgets` — é **derivado** dentro de `view()` a cada render. Isso é intencional: menos estado para gerenciar, menos bugs.

### Por que `key` em cada widget?

O reconciliador usa `key` para identificar widgets entre renders. Sem `key`, uma lista de voltas crescendo causaria remontar os nós errados. Com `key=f"lap-{i}"`, cada volta permanece estável no DOM mesmo quando novas são adicionadas.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar **estado temporal determinístico** com décimos de segundo inteiros
- ✅ Usar `app.set_state(mutador)` com funções internas para mutações complexas
- ✅ Criar **renderização condicional** com `*([widget] if cond else [])`
- ✅ Usar `key` estável em listas dinâmicas para o reconciliador funcionar corretamente
- ✅ Separar **estado** (mínimo) de **valores derivados** (calculados em `view`)
- ✅ Escrever um helper de formatação puro e testável fora da UI

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um **contador de melhor volta** que destaca a volta mais rápida em azul
- 💡 Conecte um timer real com `asyncio.sleep(0.1)` no Modo B (veja [Modos de execução](../tutorial/modes.md))
- 💡 Explore o [Tutorial — o Counter](../tutorial/index.md) para ver o padrão `set_state` mais simples
- 💡 Explore o [Todo no tutorial](../tutorial/state.md) para outro exemplo de lista dinâmica com `key`
