# Controls: fields, switches, sliders and pickers

A form is made of controls, and every control has two halves: what it **draws**
and what it **reports**. In tempestweb you declare the core's widget; the
renderer picks the native HTML element and the client reports the event your
handler declared.

This page is the map of both halves. 🚀

## The principle: the browser already knows how

Every core control becomes the element the browser already knows how to operate —
with the keyboard, focus, a screen reader and, on a phone, the right keyboard and
picker:

| Widget | Element | Event → handler | What arrives |
|---|---|---|---|
| `Input` | `<input>` | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `TextArea` | `<textarea>` | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `MaskedInput` | `<input>` + mask | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `PinInput` | `<input>` + `one-time-code` | `input` → `on_change`, `complete` | `TextChangeEvent(value)` |
| `Checkbox` | `<label>` + `<input type=checkbox>` | `change` → `on_change` | `ToggleEvent(checked)` |
| `Switch` | `<label>` + checkbox with `role=switch` | `change` → `on_change` | `ToggleEvent(checked)` |
| `Slider` | `<input type=range>` | `input`/`change` → `on_change` | `SlideEvent(value)` |
| `RangeSlider` | two `<input type=range>` | `input`/`change` → `on_change` | `RangeChangeEvent(low, high)` |
| `Dropdown` | `<select>` + `<option>` | `change` → `on_select` | `SelectEvent(value, index)` |
| `Autocomplete` | `<input>` + `<datalist>` | `input` → `on_change`, `select` → `on_select` | `TextChangeEvent` / `SelectEvent` |
| `DatePicker` | `<input type=date>` | `change` → `on_change` | `DateChangeEvent(value)` |
| `TimePicker` | `<input type=time>` | `change` → `on_change` | `TimeChangeEvent(value)` |
| `FilePicker` | `<input type=file>` | `change` → `on_select` | `FileSelectEvent(uri, name)` |
| `TabBar` | `role=tablist` + `role=tab` | `click` → `on_change` | `RouteChangeEvent(name, params)` |

The same in all three modes: the renderer (`client/dom.js`) is shared by Mode A
(WASM), Mode B (server) and Mode C (transpiled).

!!! tip "The event has the widget's shape, not the DOM's"
    A `Switch` gets `event.checked`, a `Slider` gets `event.value`, a
    `RangeSlider` gets `event.low`/`event.high`. You never read
    `payload["value"]` by hand — the runtime validates the payload into the typed
    event the handler declared.

## A switch and a slider

```python
from dataclasses import dataclass

from tempest_core import App, Column, SlideEvent, Slider, Switch, Text, ToggleEvent, Widget


@dataclass
class Prefs:
    """The preferences this screen controls.

    Attributes:
        notify: Whether notifications are on.
        volume: Playback volume, in ``[0, 100]``.
    """

    notify: bool = True
    volume: float = 70.0


def make_state() -> Prefs:
    """Build the screen's initial state."""
    return Prefs()


def view(app: App[Prefs]) -> Widget:
    """Draw a switch and a slider bound to the state."""

    def toggle(event: ToggleEvent) -> None:
        app.set_state(lambda prefs: setattr(prefs, "notify", event.checked))

    def slide(event: SlideEvent) -> None:
        app.set_state(lambda prefs: setattr(prefs, "volume", event.value))

    return Column(
        key="prefs",
        children=[
            Switch(key="notify", label="Notifications", checked=app.state.notify, on_change=toggle),
            Slider(
                key="volume",
                value=app.state.volume,
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                on_change=slide,
            ),
            Text(key="reading", content=f"Volume: {app.state.volume:.0f}%"),
        ],
    )
```

That trailing `Text` is the fastest smoke test there is: move the slider, and if
the text does not change, the event never arrived.

!!! note "Why a `Switch` is a `<label>`"
    What carries the state is a real `<input type=checkbox role=switch>` inside
    the `<label>`. Space toggles it, Tab reaches it, and a screen reader announces
    "switch, on" — for free. The `label` is the element that carries the `key`; the
    input inside it belongs to the renderer.

## Choosing from a list

`Dropdown` reports `on_select` with the value **and** the index. The
`placeholder` is a disabled leading option, and it does not shift the index:

```python
from tempest_core import App, Dropdown, SelectEvent, Widget

_CABINS: list[str] = ["Economy", "Premium", "Business", "First"]


def view(app: App[Booking]) -> Widget:
    """Draw the cabin choice."""

    def choose(event: SelectEvent) -> None:
        def apply(booking: Booking) -> None:
            booking.cabin = event.value
            booking.cabin_index = event.index

        app.set_state(apply)

    return Dropdown(
        key="cabin",
        options=_CABINS,
        value=app.state.cabin,
        placeholder="Choose a cabin",
        on_select=choose,
    )
```

`Autocomplete` is the sibling that takes free text: its `options` become a
`<datalist>` the browser draws, `on_change` arrives on every keystroke, and
`on_select` arrives when the field holds exactly one of the offered options.

## Date, time and file

The three pickers use the platform's own control — the browser's calendar is
better than anything this renderer would draw, and on a phone it is the native
picker:

```python
from tempest_core import App, Column, DateChangeEvent, DatePicker, FilePicker, FileSelectEvent, Widget


def view(app: App[Booking]) -> Widget:
    """Draw the departure day and the attachment."""

    def when(event: DateChangeEvent) -> None:
        app.set_state(lambda b: setattr(b, "departure", event.value))

    def attach(event: FileSelectEvent) -> None:
        app.set_state(lambda b: setattr(b, "document", event.name or ""))

    return Column(
        key="trip",
        children=[
            DatePicker(key="departure", label="Departure", value=app.state.departure, on_change=when),
            FilePicker(key="doc", label="Attach ID", value=app.state.document, on_select=attach),
        ],
    )
```

!!! warning "A `FilePicker`'s `value` is read-only"
    No page may assign the value of an `<input type=file>` — that is a browser
    protection, not a limitation here. The `value` you pass is **displayed** next
    to the button (the renderer reflects it into an attribute the base sheet
    prints), and what arrives in `on_select` is the file's `name` plus a `blob:`
    `uri` for its bytes.

## Tabs: `TabBar` draws, `TabView` shows

They are two widgets, and that is on purpose:

```python
from tempest_core import App, Column, RouteChangeEvent, TabBar, TabView, Widget

_TABS: list[str] = ["Overview", "Activity", "Settings"]


def view(app: App[Profile]) -> Widget:
    """Draw the tab strip above the panel."""

    def switch(event: RouteChangeEvent) -> None:
        app.set_state(lambda p: setattr(p, "tab", int(event.params.get("index", 0))))

    return Column(
        key="profile",
        children=[
            TabBar(key="tabs", tabs=_TABS, active=app.state.tab, on_change=switch),
            TabView(key="panel", tabs=_TABS, active=app.state.tab, child=_section(app.state)),
        ],
    )
```

!!! info "Technical details — why a `TabView` does not draw its own tabs"
    A `TabView` holds an **IR child** (the panel), and a patch path addresses a
    child by index. A renderer-owned tab strip would take index 0 and every later
    patch would point at the wrong element — that is the contract's rule: a
    renderer-owned child is only legal inside an IR leaf.

    A `TabBar` **is** a leaf, so it may draw its own buttons. What the `TabView`
    does is tell the truth about the state: `role="tabpanel"` plus the active
    tab's name in `aria-label`. Wire both to the same handler, as above.

    The same holds for `RouteDrawer`: it holds two IR children (content and
    drawer), so its `open` becomes the `data-tw-open` attribute the base sheet
    uses to slide the drawer over the content. Toggling it is your own button.

## Recap

* Every core control becomes the equivalent native element — keyboard, focus and
  a11y come from the browser.
* The handler receives the **widget's typed event** (`checked`, `value`,
  `low`/`high`, `value`/`index`), never a raw dict.
* `Dropdown` and `FilePicker` report `on_select`; the other fields report
  `on_change`.
* `TabBar` draws the strip, `TabView` shows the panel, and both share the handler.
* A summary `Text` next to the form is the quickest way to prove the two-way
  binding works — which is what the [Booking form](../examples/booking-form.md)
  example does.
