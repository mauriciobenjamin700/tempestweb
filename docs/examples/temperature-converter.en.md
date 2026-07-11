# Temperature Converter

Learn how to build **two synchronized fields** — Celsius and Fahrenheit — that
update each other as you type. 🌡️

By the end of this tutorial you'll have a complete app demonstrating **two-way
binding** using `Input`, `TextChangeEvent`, and `set_state`, with no extra
libraries.

---

## The problem

Imagine two text fields: one for Celsius, one for Fahrenheit. The user edits
either one and the other must update instantly — no "Convert" button needed.
This pattern — **bidirectional binding** — is one of the most classic patterns
in reactive programming.

There's an extra challenge: text fields go through partial states. The user
might type `"-"`, `"36."`, or clear the field entirely. The app must survive
all of that without crashing or showing `"nan"`.

!!! note "What you'll practise"
    - `Input` as a **controlled component** (its `value` comes from state).
    - `TextChangeEvent` — the typed event that crosses the Python ↔ renderer boundary.
    - `set_state` with a mutation function that updates **two fields at once** (atomically).
    - Graceful handling of non-numeric input with `try/except ValueError`.

---

## Prerequisites

Make sure you've completed [Installation](../installation.md) and read the
[Counter Tutorial](../tutorial/index.md) — this example assumes you already
know `Column`, `Row`, `Text`, `App`, `make_state`, and `view`.

---

## The complete app

This is the exact code from
[`examples/temperature-converter/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/temperature-converter/app.py).
Copy it, run it, then read the piece-by-piece explanation below.

```python
"""Temperature Converter — demonstrates two-way binding via on_change.

Two :class:`~tempest_core.widgets.Input` fields (Celsius and Fahrenheit)
stay in sync: editing either one recomputes and writes the other into state,
driven entirely by :class:`~tempest_core.widgets.events.TextChangeEvent`.
No transport is named — the same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

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

## Piece by piece

### 1. State as `str`, not `float`

```python
@dataclass
class ConverterState:
    celsius: str = "0"
    fahrenheit: str = "32"
```

Why `str` instead of `float`? Because the user types into the field one
character at a time. At some point the field may contain `"-"`, `"36."`, or be
completely empty — all **valid in-progress states** that cannot be parsed to
`float`. Storing as `str` makes the state mirror exactly what is in the field,
without breaking.

!!! tip "Tip"
    This is the same approach used in React (controlled inputs) and Flutter
    (`TextEditingController`): state holds the raw string; conversion to a
    number only happens when you need to calculate.

---

### 2. Pure conversion functions

```python
_C_TO_F_SCALE: float = 9.0 / 5.0
_F_TO_C_SCALE: float = 5.0 / 9.0
_F_OFFSET: float = 32.0


def _celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * _C_TO_F_SCALE + _F_OFFSET


def _fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - _F_OFFSET) * _F_TO_C_SCALE
```

Pure functions, no side effects. They take a `float` and return a `float` —
easy to test in isolation. Keeping the math **outside** the handlers makes
`view` readable at a glance.

---

### 3. Formatting without unnecessary zeros

```python
def _format(value: float) -> str:
    rounded: str = f"{value:.2f}".rstrip("0").rstrip(".")
    return rounded
```

`f"{value:.2f}"` caps at two decimal places. The double `rstrip` removes
trailing zeros and a dangling dot: `"100.00"` → `"100"`, `"36.67"` stays
`"36.67"`. The user sees a clean number, not `"36.670000"`.

---

### 4. `TextChangeEvent` and the Celsius handler

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

`TextChangeEvent` is the typed event the renderer (DOM or server) fires every
time the text inside an `Input` changes. It carries `event.value` with the
current field content.

The `try/except ValueError` block is the heart of error tolerance:

- If `new_celsius` is `"100"`, `float("100")` → `100.0` → `212.0` → `"212"`. ✅
- If `new_celsius` is `"-"` or `""`, `float("-")` raises `ValueError` → `new_fahrenheit = ""`. ✅

The `_mutate` function receives the current state and **writes both fields at
once**. `set_state` guarantees the rebuild happens only after the mutation is
complete — there is no "intermediate state" where Celsius changed but
Fahrenheit hasn't yet.

!!! info "Why `_mutate` inside the handler?"
    Capturing `new_celsius` and `new_fahrenheit` via closure ensures the
    mutation function always applies the values computed **for that specific
    event**, even if multiple events arrive before the next rebuild.

---

### 5. The Fahrenheit handler — the mirror image

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

Exactly symmetric to the previous handler, but in reverse. Each handler owns
its own field — it reads its own, recomputes the other.

---

### 6. Controlled `Input` widgets in the view tree

```python
Input(
    key="celsius-input",
    value=app.state.celsius,
    placeholder="e.g. 100",
    on_change=on_celsius_change,
),
```

The `Input` is a **controlled component**: `value=app.state.celsius` tells the
renderer to overwrite the field with the state value on every rebuild. The
user types → `on_change` fires → `set_state` updates state → rebuild →
`value` is re-applied. The field can never drift out of sync with the state.

!!! warning "Warning"
    Without `value=` the `Input` becomes **uncontrolled**: the renderer won't
    restore the text after each rebuild, and the two-way binding breaks.
    Always pass `value=` when you need full control over the field contents.

---

### 7. The conditional summary text

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

If either field is empty (partial input), a neutral message is displayed
instead of `" °C =  °F"`. A simple inline `if` expression on `content` is
enough — no extra logic outside `view`.

---

## Running the app 🚀

Save the file as `examples/temperature-converter/app.py` and pick a mode:

=== "WASM mode (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm examples/temperature-converter/app.py
    ```

    Pyodide loads the full Python runtime in the browser. No server, no
    WebSocket — the Python handler runs locally in the tab.

=== "Server mode (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/temperature-converter/app.py
    ```

    A FastAPI server starts locally. The JS client connects via WebSocket,
    sends typing events, and receives patches back.

!!! check "Same code, two modes"
    Notice that `app.py` never mentions `wasm` or `server` anywhere.
    The transport boundary lives entirely inside `tempestweb` — you only
    choose at launch time.

Open your browser at `http://localhost:8000`. Type `100` in the Celsius field
and watch `212` appear in Fahrenheit instantly. Type `32` in Fahrenheit and
see `0` appear in Celsius. 🌡️

---

## Recap

In this example you learned:

- ✅ **State as `str`** — text fields should mirror raw text to support partial edits.
- ✅ **`TextChangeEvent`** — the typed event that delivers the new text to the Python handler.
- ✅ **Atomic mutation** — `set_state(_mutate)` updates two fields at once, preventing intermediate state.
- ✅ **`try/except ValueError`** — graceful handling of non-numeric input without crashing the app.
- ✅ **Controlled `Input`** — `value=app.state.X` is required to keep the field in sync with state.
- ✅ **Purity outside `view`** — conversion and formatting functions outside the handlers make the code testable and readable.

---

## Next steps

- Read the [Counter Tutorial](../tutorial/index.md) if you haven't yet — it
  explains `set_state` and the rebuild cycle in more depth.
- See how [Patches over the wire](../tutorial/patches.md) describes exactly
  which operations the reconciler emits when both fields change together.
- Explore other examples in the **Examples** section to discover more state
  patterns and widget composition techniques.
