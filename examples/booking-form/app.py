"""Booking form — the pickers, the range and the dropdown, bound to state.

Every control here is one the renderer used to draw as an anonymous ``<div>``
(tempestweb#143), so this example exists to make them exercisable in a real
browser:

* :class:`~tempest_core.widgets.inputs.DatePicker` — the departure day.
* :class:`~tempest_core.widgets.inputs.TimePicker` — the boarding time.
* :class:`~tempest_core.widgets.inputs.RangeSlider` — the fare window, two
  thumbs reported as one ``low``/``high`` pair.
* :class:`~tempest_core.widgets.inputs.Dropdown` — the cabin, reported as a
  ``SelectEvent`` carrying the chosen option and its index.
* :class:`~tempest_core.widgets.inputs.FilePicker` — an attachment, reported as
  a ``FileSelectEvent`` with the file's name and a blob URI.

Every change re-renders the summary card at the bottom, so the two-way binding
is visible rather than asserted.

Run unchanged in all three modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
    tempestweb build --mode transpile   # the same view, compiled to JS
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import (
    App,
    AppBar,
    Card,
    Column,
    DateChangeEvent,
    DatePicker,
    Divider,
    Dropdown,
    Edge,
    FilePicker,
    FileSelectEvent,
    FontWeight,
    RangeChangeEvent,
    RangeSlider,
    Scaffold,
    SelectEvent,
    Style,
    Text,
    TimeChangeEvent,
    TimePicker,
    Widget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CABINS: list[str] = ["Economy", "Premium", "Business", "First"]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class BookingState:
    """Everything the form collects.

    Attributes:
        departure: Departure day, in the ISO spelling the native date input uses.
        boarding: Boarding time, ``HH:MM``.
        fare_low: Lower end of the acceptable fare window, in BRL.
        fare_high: Upper end of the acceptable fare window, in BRL.
        cabin: The chosen cabin, one of ``_CABINS``.
        cabin_index: Its position in ``_CABINS`` (what a ``SelectEvent`` reports).
        document: Name of the attached document, or ``""`` when none was picked.
    """

    departure: str = "2026-09-14"
    boarding: str = "07:30"
    fare_low: float = 400.0
    fare_high: float = 1800.0
    cabin: str = "Economy"
    cabin_index: int = 0
    document: str = ""


def make_state() -> BookingState:
    """Build the initial booking state.

    Returns:
        A fresh :class:`BookingState` with a plausible trip pre-filled.
    """
    return BookingState()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _when_card(app: App[BookingState]) -> Widget:
    """Build the date + time card.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A card holding the departure DatePicker and the boarding TimePicker.
    """

    def on_departure(event: DateChangeEvent) -> None:
        """Store the chosen departure day.

        Args:
            event: The date-change event carrying the ISO ``value``.
        """
        app.set_state(lambda s: setattr(s, "departure", event.value))

    def on_boarding(event: TimeChangeEvent) -> None:
        """Store the chosen boarding time.

        Args:
            event: The time-change event carrying the ``HH:MM`` ``value``.
        """
        app.set_state(lambda s: setattr(s, "boarding", event.value))

    return Card(
        key="when-card",
        children=[
            Text(
                content="When",
                key="when-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            DatePicker(
                key="departure",
                label="Departure",
                value=app.state.departure,
                on_change=on_departure,
            ),
            TimePicker(
                key="boarding",
                label="Boarding",
                value=app.state.boarding,
                on_change=on_boarding,
            ),
        ],
    )


def _fare_card(app: App[BookingState]) -> Widget:
    """Build the fare-window card.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A card holding the fare RangeSlider and its current reading.
    """

    def on_fare(event: RangeChangeEvent) -> None:
        """Store both ends of the fare window.

        Args:
            event: The range-change event carrying ``low`` and ``high``.
        """

        def apply(state: BookingState) -> None:
            """Write the reported window onto the state.

            Args:
                state: The state being mutated.
            """
            state.fare_low = event.low
            state.fare_high = event.high

        app.set_state(apply)

    return Card(
        key="fare-card",
        children=[
            Text(
                content="Fare window",
                key="fare-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content=(f"R$ {app.state.fare_low:.0f} — R$ {app.state.fare_high:.0f}"),
                key="fare-reading",
                style=Style(font_size=13.0),
            ),
            RangeSlider(
                key="fare",
                low=app.state.fare_low,
                high=app.state.fare_high,
                min_value=0.0,
                max_value=4000.0,
                step=50.0,
                on_change=on_fare,
            ),
        ],
    )


def _cabin_card(app: App[BookingState]) -> Widget:
    """Build the cabin + attachment card.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A card holding the cabin Dropdown and the document FilePicker.
    """

    def on_cabin(event: SelectEvent) -> None:
        """Store the chosen cabin and its index.

        Args:
            event: The select event carrying the option ``value`` and ``index``.
        """

        def apply(state: BookingState) -> None:
            """Write the chosen cabin onto the state.

            Args:
                state: The state being mutated.
            """
            state.cabin = event.value
            state.cabin_index = event.index

        app.set_state(apply)

    def on_document(event: FileSelectEvent) -> None:
        """Store the attached document's name.

        Args:
            event: The file-select event carrying the file ``name`` and ``uri``.
        """
        app.set_state(lambda s: setattr(s, "document", event.name or ""))

    return Card(
        key="cabin-card",
        children=[
            Text(
                content="Cabin & documents",
                key="cabin-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Dropdown(
                key="cabin",
                options=_CABINS,
                value=app.state.cabin,
                placeholder="Choose a cabin",
                on_select=on_cabin,
            ),
            FilePicker(
                key="document",
                label="Attach ID",
                value=app.state.document,
                on_select=on_document,
            ),
        ],
    )


def _summary_card(state: BookingState) -> Widget:
    """Build the live summary of everything picked so far.

    Args:
        state: The current booking state.

    Returns:
        A card that re-renders on every change, making the binding visible.
    """
    document = state.document or "none"
    return Card(
        key="summary-card",
        children=[
            Text(
                content="Live summary",
                key="summary-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="summary-divider"),
            Text(
                content=f"Departure: {state.departure} at {state.boarding}",
                key="summary-when",
                style=Style(font_size=13.0),
            ),
            Text(
                content=(
                    f"Cabin: {state.cabin} (#{state.cabin_index})"
                    f"  |  Fare: R$ {state.fare_low:.0f}–{state.fare_high:.0f}"
                ),
                key="summary-cabin",
                style=Style(font_size=13.0),
            ),
            Text(
                content=f"Document: {document}",
                key="summary-document",
                style=Style(font_size=13.0),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[BookingState]) -> Widget:
    """Render the booking form from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    return Scaffold(
        key="booking-scaffold",
        app_bar=AppBar(title="Book a trip", key="booking-appbar"),
        body=Column(
            key="booking-body",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _when_card(app),
                _fare_card(app),
                _cabin_card(app),
                _summary_card(app.state),
            ],
        ),
    )
