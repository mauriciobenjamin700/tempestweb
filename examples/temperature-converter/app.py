"""Temperature Converter — demonstrates two-way binding via on_change.

Two :class:`~tempestweb._core.widgets.Input` fields (Celsius and Fahrenheit)
stay in sync: editing either one recomputes and writes the other into state,
driven entirely by :class:`~tempestweb._core.widgets.events.TextChangeEvent`.
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

from tempestweb._core.style import Edge
from tempestweb._core.widgets.events import TextChangeEvent

from tempestweb._core import App, Column, Row, Style, Text, Widget
from tempestweb._core.widgets import Input

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

    Both :class:`~tempestweb._core.widgets.Input` fields are controlled
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
