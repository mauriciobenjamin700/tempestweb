# Conversor de Temperatura

Aprenda a criar **dois campos sincronizados** — Celsius e Fahrenheit — que se
atualizam mutuamente enquanto você digita. 🌡️

Ao final deste tutorial você terá um app completo com **two-way binding** usando
`Input`, `TextChangeEvent` e `set_state`, sem nenhuma biblioteca extra.

---

## O problema

Imagine dois campos de texto: um para Celsius, outro para Fahrenheit. O
usuário edita qualquer um dos dois e o outro deve se atualizar na hora, sem
botão de "converter". Esse padrão — **binding bidirecional** — é um dos mais
clássicos da programação reativa.

O desafio extra é que campos de texto passam por estados parciais: o usuário
pode digitar `"-"`, `"36."` ou simplesmente apagar tudo. O app precisa
sobreviver a isso sem travar ou exibir `"nan"`.

!!! note "O que você vai exercitar"
    - `Input` como componente **controlado** (o `value` vem do estado).
    - `TextChangeEvent` — o evento tipado que cruza a fronteira Python ↔ renderizador.
    - `set_state` com uma função de mutação que atualiza **dois campos de uma vez** (atomicamente).
    - Tratamento gracioso de entrada não-numérica com `try/except ValueError`.

---

## Pré-requisitos

Antes de continuar, certifique-se de ter feito a
[Instalação](../installation.md) e lido o
[Tutorial do Counter](../tutorial/index.md) — este exemplo assume que você já
conhece `Column`, `Row`, `Text`, `App`, `make_state` e `view`.

---

## O app completo

Este é o código exato de
[`examples/temperature-converter/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/temperature-converter/app.py).
Copie, rode, e depois leia a explicação linha por linha.

```python
"""Temperature Converter — demonstrates two-way binding via on_change.

Two :class:`~tempest_core.widgets.Input` fields (Celsius and Fahrenheit)
stay in sync: editing either one recomputes and writes the other into state,
driven entirely by :class:`~tempest_core.widgets.events.TextChangeEvent`.
No transport is named — the same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

Key patterns shown:

* **Two-way (derived) state** — ``celsius`` and ``fahrenheit`` are kept as
  ``str`` so the fields can hold mid-edit values (e.g. ``"-"``) without
  crashing.  Each on_change handler parses its own field, recomputes the
  other, and writes both back atomically.
* **TextChangeEvent** — the typed event crossing the Python↔renderer boundary.
* **Graceful parse failure** — if the user types a non-numeric value the
  opposite field is cleared to ``""`` rather than displaying ``"nan"`` or
  raising.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Input
from tempest_core.widgets.events import TextChangeEvent

__all__ = ["ConverterState", "make_state", "view"]

_C_TO_F_SCALE: float = 9.0 / 5.0
_F_TO_C_SCALE: float = 5.0 / 9.0
_F_OFFSET: float = 32.0


def _celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a Celsius temperature to Fahrenheit.

    Args:
        celsius: Temperature in degrees Celsius.

    Returns:
        The equivalent temperature in degrees Fahrenheit.
    """
    return celsius * _C_TO_F_SCALE + _F_OFFSET


def _fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert a Fahrenheit temperature to Celsius.

    Args:
        fahrenheit: Temperature in degrees Fahrenheit.

    Returns:
        The equivalent temperature in degrees Celsius.
    """
    return (fahrenheit - _F_OFFSET) * _F_TO_C_SCALE


def _format(value: float) -> str:
    """Format a floating-point temperature for display.

    Strips trailing zeros so ``"100.0"`` becomes ``"100"`` and
    ``"36.6666…"`` becomes ``"36.67"``.

    Args:
        value: The temperature value to format.

    Returns:
        A compact, human-readable string representation.
    """
    rounded: str = f"{value:.2f}".rstrip("0").rstrip(".")
    return rounded


@dataclass
class ConverterState:
    """Mutable state for the temperature converter.

    Both fields are stored as strings so the inputs can hold in-progress
    edits (e.g. a bare ``"-"`` or ``"36."``).

    Attributes:
        celsius: The current Celsius field value.
        fahrenheit: The current Fahrenheit field value.
    """

    celsius: str = "0"
    fahrenheit: str = "32"


def make_state() -> ConverterState:
    """Build the initial state for the temperature converter.

    Returns:
        A fresh :class:`ConverterState` initialised to 0 °C / 32 °F.
    """
    return ConverterState()


def view(app: App[ConverterState]) -> Widget:
    """Render the temperature converter UI from the current state.

    Both :class:`~tempest_core.widgets.Input` fields are controlled
    components: their ``value`` comes from state, and their ``on_change``
    handlers write back to state — including recomputing the *other* field.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_celsius_change(event: TextChangeEvent) -> None:
        """Handle an edit to the Celsius field.

        Parses the new value and recomputes Fahrenheit.  If parsing fails,
        Fahrenheit is reset to ``""`` to avoid displaying garbage.

        Args:
            event: The change event carrying the new text value.
        """
        new_celsius: str = event.value

        try:
            fahrenheit_val: float = _celsius_to_fahrenheit(float(new_celsius))
            new_fahrenheit: str = _format(fahrenheit_val)
        except ValueError:
            new_fahrenheit = ""

        def _mutate(s: ConverterState) -> None:
            s.celsius = new_celsius
            s.fahrenheit = new_fahrenheit

        app.set_state(_mutate)

    def on_fahrenheit_change(event: TextChangeEvent) -> None:
        """Handle an edit to the Fahrenheit field.

        Parses the new value and recomputes Celsius.  If parsing fails,
        Celsius is reset to ``""`` to avoid displaying garbage.

        Args:
            event: The change event carrying the new text value.
        """
        new_fahrenheit: str = event.value

        try:
            celsius_val: float = _fahrenheit_to_celsius(float(new_fahrenheit))
            new_celsius: str = _format(celsius_val)
        except ValueError:
            new_celsius = ""

        def _mutate(s: ConverterState) -> None:
            s.fahrenheit = new_fahrenheit
            s.celsius = new_celsius

        app.set_state(_mutate)

    return Column(
        key="root",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=[
            Text(
                content="Temperature Converter",
                key="title",
            ),
            Row(
                key="fields",
                style=Style(gap=12.0),
                children=[
                    Column(
                        key="celsius-col",
                        style=Style(gap=4.0),
                        children=[
                            Text(content="Celsius (°C)", key="celsius-label"),
                            Input(
                                key="celsius-input",
                                value=app.state.celsius,
                                placeholder="e.g. 100",
                                on_change=on_celsius_change,
                            ),
                        ],
                    ),
                    Column(
                        key="fahrenheit-col",
                        style=Style(gap=4.0),
                        children=[
                            Text(content="Fahrenheit (°F)", key="fahrenheit-label"),
                            Input(
                                key="fahrenheit-input",
                                value=app.state.fahrenheit,
                                placeholder="e.g. 212",
                                on_change=on_fahrenheit_change,
                            ),
                        ],
                    ),
                ],
            ),
            Text(
                content=(
                    f"{app.state.celsius} °C = {app.state.fahrenheit} °F"
                    if app.state.celsius and app.state.fahrenheit
                    else "Enter a temperature above to convert."
                ),
                key="summary",
            ),
        ],
    )
```

---

## Explicando peça por peça

### 1. Estado como `str`, não `float`

```python
@dataclass
class ConverterState:
    celsius: str = "0"
    fahrenheit: str = "32"
```

Por que `str` e não `float`? Porque o usuário digita no campo de texto
caractere por caractere. Em algum momento o campo pode conter `"-"`, `"36."` ou
estar completamente vazio — todos estados **válidos durante a edição** que não
se convertem para `float`. Guardar como `str` faz o estado espelhar exatamente
o que está no campo, sem quebrar.

!!! tip "Dica"
    Essa é a mesma abordagem usada em React (inputs controlados) e Flutter
    (`TextEditingController`): o estado é a string bruta; a conversão para
    número acontece só na hora de calcular.

---

### 2. As funções de conversão puras

```python
_C_TO_F_SCALE: float = 9.0 / 5.0
_F_TO_C_SCALE: float = 5.0 / 9.0
_F_OFFSET: float = 32.0


def _celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * _C_TO_F_SCALE + _F_OFFSET


def _fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - _F_OFFSET) * _F_TO_C_SCALE
```

Funções puras, sem estado. Elas só recebem `float` e devolvem `float` — fáceis
de testar isoladamente. Os cálculos ficam **fora** do handler para o `view`
permanecer legível.

---

### 3. Formatação sem zeros desnecessários

```python
def _format(value: float) -> str:
    rounded: str = f"{value:.2f}".rstrip("0").rstrip(".")
    return rounded
```

`f"{value:.2f}"` garante no máximo duas casas decimais. O duplo `rstrip` remove
os zeros e o ponto sobrando: `"100.00"` → `"100"`, `"36.67"` permanece
`"36.67"`. O usuário vê um número limpo, não `"36.670000"`.

---

### 4. O `TextChangeEvent` e o handler de Celsius

```python
def on_celsius_change(event: TextChangeEvent) -> None:
    new_celsius: str = event.value

    try:
        fahrenheit_val: float = _celsius_to_fahrenheit(float(new_celsius))
        new_fahrenheit: str = _format(fahrenheit_val)
    except ValueError:
        new_fahrenheit = ""

    def _mutate(s: ConverterState) -> None:
        s.celsius = new_celsius
        s.fahrenheit = new_fahrenheit

    app.set_state(_mutate)
```

`TextChangeEvent` é o evento tipado que o renderizador (DOM ou servidor)
dispara sempre que o texto de um `Input` muda. Ele carrega `event.value` com
o conteúdo atual do campo.

O bloco `try/except ValueError` é o coração da tolerância a erros:

- Se `new_celsius` é `"100"`, `float("100")` → `100.0` → `212.0` → `"212"`. ✅
- Se `new_celsius` é `"-"` ou `""`, `float("-")` levanta `ValueError` → `new_fahrenheit = ""`. ✅

A função `_mutate` recebe o estado atual e **escreve os dois campos de uma
vez**. `set_state` garante que o rebuild acontece apenas depois da mutação
completa — não há "estado intermediário" onde Celsius mudou mas Fahrenheit
ainda não.

!!! info "Por que `_mutate` dentro do handler?"
    Capturar `new_celsius` e `new_fahrenheit` via closure garante que a
    função de mutação sempre aplica os valores calculados **naquele evento**,
    mesmo que múltiplos eventos cheguem em sequência antes do próximo rebuild.

---

### 5. O handler de Fahrenheit — o espelho

```python
def on_fahrenheit_change(event: TextChangeEvent) -> None:
    new_fahrenheit: str = event.value

    try:
        celsius_val: float = _fahrenheit_to_celsius(float(new_fahrenheit))
        new_celsius: str = _format(celsius_val)
    except ValueError:
        new_celsius = ""

    def _mutate(s: ConverterState) -> None:
        s.fahrenheit = new_fahrenheit
        s.celsius = new_celsius

    app.set_state(_mutate)
```

Exatamente simétrico ao anterior, mas no sentido inverso. Cada handler é dono
do seu campo — lê o próprio, recalcula o outro.

---

### 6. Os `Input` controlados na árvore de view

```python
Input(
    key="celsius-input",
    value=app.state.celsius,
    placeholder="e.g. 100",
    on_change=on_celsius_change,
),
```

O `Input` é um **componente controlado**: `value=app.state.celsius` faz o
renderizador sobrescrever o campo com o valor do estado a cada rebuild. O
usuário digita → `on_change` dispara → `set_state` atualiza o estado → rebuild
→ `value` é re-aplicado. O campo nunca "sai de sincronia" com o estado.

!!! warning "Aviso"
    Sem `value=` o `Input` seria **não-controlado**: o renderizador não
    restauraria o texto após cada rebuild, e o binding bidirecional quebraria.
    Sempre passe `value=` quando você precisar de controle total sobre o
    conteúdo do campo.

---

### 7. O texto de resumo condicional

```python
Text(
    content=(
        f"{app.state.celsius} °C = {app.state.fahrenheit} °F"
        if app.state.celsius and app.state.fahrenheit
        else "Enter a temperature above to convert."
    ),
    key="summary",
),
```

Se algum dos dois campos estiver vazio (entrada parcial), exibe uma mensagem
neutra em vez de `" °C =  °F"`. Uma `if` expressão inline no `content` é
suficiente — sem lógica extra fora da `view`.

---

## Rodando o app 🚀

Salve o arquivo em `examples/temperature-converter/app.py` e escolha o modo:

=== "Modo WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/temperature-converter
    ```

    O Pyodide carrega o Python completo no browser. Sem servidor, sem
    WebSocket — o handler Python roda localmente no tab.

=== "Modo Server (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/temperature-converter
    ```

    Um servidor FastAPI sobe localmente. O cliente JS conecta via WebSocket,
    envia os eventos de digitação e recebe patches de volta.

!!! check "Mesmo código, dois modos"
    Repare que o `app.py` não menciona `wasm` nem `server` em nenhum lugar.
    A fronteira de transporte fica completamente dentro do `tempestweb` — você
    só escolhe no momento de rodar.

Abra o browser em `http://localhost:8000`. Digite `100` no campo Celsius e
veja `212` aparecer no Fahrenheit imediatamente. Digite `32` no Fahrenheit e
veja `0` surgir no Celsius. 🌡️

---

## Recapitulando

Neste exemplo você aprendeu:

- ✅ **Estado como `str`** — campos de texto devem espelhar o texto bruto para suportar edições parciais.
- ✅ **`TextChangeEvent`** — o evento tipado que entrega o novo texto ao handler Python.
- ✅ **Mutação atômica** — `set_state(_mutate)` atualiza dois campos de uma vez, evitando estado intermediário.
- ✅ **`try/except ValueError`** — tratamento gracioso de entrada não-numérica sem travar o app.
- ✅ **`Input` controlado** — `value=app.state.X` é obrigatório para manter o campo em sincronia com o estado.
- ✅ **Pureza fora do `view`** — funções de conversão e formatação fora dos handlers deixam o código testável e legível.

---

## Próximos passos

- Leia o [Tutorial do Counter](../tutorial/index.md) se ainda não o fez — ele
  explica `set_state` e o ciclo de rebuild com mais profundidade.
- Veja como [Patches na rede](../tutorial/patches.md) descrevem exatamente
  quais operações o reconciliador emite quando os dois campos mudam juntos.
- Explore outros exemplos na seção **Exemplos** para ver mais padrões de
  estado e composição de widgets.
