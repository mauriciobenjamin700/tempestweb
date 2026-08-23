# Booking Form — Pickers, a Fare Range and an Attachment 🚀

A booking form with **DatePicker**, **TimePicker**, **RangeSlider**, **Dropdown**
and **FilePicker** — the controls that lean on the browser's native widget — all
bound to a single state dataclass.

---

## What you will build

Three cards plus a live summary:

| Card | Widgets | What it collects |
|---|---|---|
| **When** | `DatePicker` + `TimePicker` | departure day and boarding time |
| **Fare window** | `RangeSlider` | the acceptable price range (two values) |
| **Cabin & documents** | `Dropdown` + `FilePicker` | the chosen cabin and an attached document |
| **Live summary** | `Card` (read-only) | an immediate reflection of everything above |

Every change re-renders the summary. Pick a date and if the summary does not
move, the event never arrived — the fastest smoke test there is.

!!! tip "Why these five controls together"
    Each one is a control the browser draws better than any reimplementation: the
    calendar, the clock, the file picker. On a phone, each opens the system's own
    picker. This example exists so you can exercise them for real, in a real
    browser.

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading first:

- [Basic tutorial](../tutorial/index.md) — `App`, `view` and `set_state`
- [Controls](../tutorial/controls.md) — the widget → element → event map

---

## The state

One dataclass, one field per control. Note the `RangeSlider`'s `low`/`high` pair
and `cabin_index`, which is the index a `SelectEvent` reports:

```python
from dataclasses import dataclass


@dataclass
class BookingState:
    """Everything the form collects.

    Attributes:
        departure: Departure day, in the ISO spelling the native input uses.
        boarding: Boarding time, ``HH:MM``.
        fare_low: Lower end of the acceptable fare window, in BRL.
        fare_high: Upper end of the window, in BRL.
        cabin: The chosen cabin.
        cabin_index: Its position in the list (what a ``SelectEvent`` reports).
        document: Name of the attached document, or ``""`` when none.
    """

    departure: str = "2026-09-14"
    boarding: str = "07:30"
    fare_low: float = 400.0
    fare_high: float = 1800.0
    cabin: str = "Economy"
    cabin_index: int = 0
    document: str = ""


def make_state() -> BookingState:
    """Build the initial state, with a plausible trip pre-filled."""
    return BookingState()
```

---

## Date and time

Both pickers take and return **ISO text** — the same format the native input
uses, so there is no conversion in between:

```python
from tempest_core import App, Card, DateChangeEvent, DatePicker, TimeChangeEvent, TimePicker, Widget


def _when_card(app: App[BookingState]) -> Widget:
    """The departure-day and boarding-time card."""

    def on_departure(event: DateChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "departure", event.value))

    def on_boarding(event: TimeChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "boarding", event.value))

    return Card(
        key="when-card",
        children=[
            DatePicker(key="departure", label="Departure", value=app.state.departure, on_change=on_departure),
            TimePicker(key="boarding", label="Boarding", value=app.state.boarding, on_change=on_boarding),
        ],
    )
```

!!! note "The caption comes before the control"
    A picker's `label` is its visible caption, and it names the field for a screen
    reader natively (the control lives inside a `<label>`). On a narrow screen the
    caption wraps onto the line above instead of pushing the page sideways.

---

## The fare window

A `RangeSlider` has **two** values, and the event carries both at once — always
normalized, with `low <= high`, even if you drag one thumb past the other:

```python
from tempest_core import App, Card, RangeChangeEvent, RangeSlider, Text, Widget


def _fare_card(app: App[BookingState]) -> Widget:
    """The fare-window card, with a live reading."""

    def on_fare(event: RangeChangeEvent) -> None:
        def apply(state: BookingState) -> None:
            state.fare_low = event.low
            state.fare_high = event.high

        app.set_state(apply)

    return Card(
        key="fare-card",
        children=[
            Text(key="fare-reading", content=f"R$ {app.state.fare_low:.0f} — R$ {app.state.fare_high:.0f}"),
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
```

---

## Cabin and attachment

`Dropdown` and `FilePicker` are the two controls that report **`on_select`**
rather than `on_change`: choosing is not editing a value.

```python
from tempest_core import App, Card, Dropdown, FilePicker, FileSelectEvent, SelectEvent, Widget

_CABINS: list[str] = ["Economy", "Premium", "Business", "First"]


def _cabin_card(app: App[BookingState]) -> Widget:
    """The cabin and document card."""

    def on_cabin(event: SelectEvent) -> None:
        def apply(state: BookingState) -> None:
            state.cabin = event.value
            state.cabin_index = event.index

        app.set_state(apply)

    def on_document(event: FileSelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "document", event.name or ""))

    return Card(
        key="cabin-card",
        children=[
            Dropdown(
                key="cabin",
                options=_CABINS,
                value=app.state.cabin,
                placeholder="Choose a cabin",
                on_select=on_cabin,
            ),
            FilePicker(key="document", label="Attach ID", value=app.state.document, on_select=on_document),
        ],
    )
```

!!! warning "The `placeholder` does not shift the index"
    A `Dropdown`'s `placeholder` is a disabled `<option>` at the front of the
    list, but `event.index` counts only the real options: choosing `"Business"`
    above reports `index=2`, not `3`.

---

## Running it

```bash
tempestweb run --mode server --path examples/booking-form --port 8000   # Python on the server
tempestweb run --mode wasm   --path examples/booking-form --port 8000   # Python in the browser
tempestweb build --mode transpile --path examples/booking-form          # a static JS bundle
```

All three serve the same `app.py`. In Mode C there is no Python running at all
and the five controls still update the state.

---

## Recap

* `DatePicker`/`TimePicker` exchange **ISO text** with the native control — no
  conversion.
* `RangeSlider` reports the normalized `low`/`high` pair in one event.
* `Dropdown` and `FilePicker` report **`on_select`**; the `Dropdown`'s index
  ignores the `placeholder`.
* A `FilePicker`'s `value` is displayed, never assigned — no page may choose a
  file on the reader's behalf.
* A live summary card proves the two-way binding better than any print.

Continue with the [Settings panel](settings-panel.md), which does the same with
`Switch`, `Checkbox` and `Slider`, and with the [Controls](../tutorial/controls.md)
page.
