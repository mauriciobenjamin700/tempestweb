# Gestures: drag, reorder, paginate

Three gestures the browser does not hand to an arbitrary element, and that
tempestweb ships as widgets: dropping one thing onto another, sorting a list by
dragging, and turning the page of a carousel. You declare the handler; the client
recognizes the gesture and reports it.

## Drag and drop

`Draggable` carries a payload; `DragTarget` accepts the drop. The pair implements
the HTML5 drag contract, so it works with mouse and trackpad without any library:

```python
from tempest_core import App, Text, Widget
from tempest_core import DragEvent
from tempest_core import Draggable, DragTarget


def view(app: App[Board]) -> Widget:
    """Render a card that can be dropped into a column."""

    def dropped(event: DragEvent) -> None:
        app.set_state(lambda state: state.move(event.data, to="done"))

    return DragTarget(
        key="done",
        on_drop=dropped,
        child=Draggable(
            key="card-7",
            drag_data="card-7",
            child=Text(content="Write the post"),
        ),
    )
```

`drag_data` is what arrives as `event.data` in `on_drop` — usually the id of what
was dragged. `on_drag` tells you the drag started, if you want to paint a
"carrying this" state.

!!! warning "`child`, not `children`"
    `Draggable` and `DragTarget` wrap **one** widget: the field is `child`.
    Passing `children=` raises `ValidationError` naming the field — the core
    rejects a kwarg it does not declare. Need several children? Put a
    `Column`/`Row` inside `child`, the way the
    [Kanban board](../examples/kanban-board.md) does.

## Reordering a list

`ReorderableList` is the case where the item does not go *somewhere else*: it
changes position within its own list. The handler receives both positions — and
moving is the app's job, because the order is state:

```python
from tempest_core import App, Container, Style, Text, Widget
from tempest_core import Edge
from tempest_core import ReorderEvent
from tempest_core import ReorderableList


def view(app: App[Tasks]) -> Widget:
    """Render a list whose rows are sorted by dragging."""

    def moved(event: ReorderEvent) -> None:
        def mutate(state: Tasks) -> None:
            task = state.tasks.pop(event.from_index)
            state.tasks.insert(event.to_index, task)

        app.set_state(mutate)

    return ReorderableList(
        key="tasks",
        style=Style(gap=8.0),
        children=[
            Container(
                key=f"task-{task}",
                style=Style(padding=Edge.all(12)),
                child=Text(content=task),
            )
            for task in app.state.tasks
        ],
        on_reorder=moved,
    )
```

* The children are ordinary widgets: the client is what marks them draggable,
  after every patch batch, and draws the grab cursor.
* Positions are computed at event time from the DOM — nothing is stamped onto the
  item. A stamped index would go stale the moment the list changed.
* Dropping a row back where it came from reports nothing.

!!! tip "Give every row a `key`"
    The key is what lets the reconciler turn a reorder into a minimal
    remove/insert instead of rewriting every row.

## A paged carousel

`PageView` shows one child at a time and declares `page` + `on_page_change`. It is
a horizontal scroller with *snapping*, which gets you swipe on touch, trackpad and
`shift`+wheel — the browser is good at this. What it does not do is say which page
you landed on; that is what the client reports.

```python
from tempest_core import PageChangeEvent
from tempest_core import PageView


def view(app: App[Tour]) -> Widget:
    """Render a three-slide tour with dots and a Next button."""

    def changed(event: PageChangeEvent) -> None:
        app.set_state(lambda state: setattr(state, "page", event.page))

    return PageView(
        key="tour",
        page=app.state.page,
        children=[_slide(index) for index in range(3)],
        on_page_change=changed,
    )
```

It works both ways: the reader swipes and the state's `page` follows; the app
moves `page` (a "Next" button, say) and the carousel scrolls there.

!!! note "The report waits for the scroll to stop"
    A scroll is a stream of events, and the intermediate positions round to the
    page being *left*. Reporting those made the app fight itself — press "Next",
    the carousel starts moving, and the first intermediate event said "back to the
    previous page". So the page is only reported after a moment of quiet, once the
    carousel has settled.

## Pointer gestures: tap, drag, pinch

`GestureDetector` recognizes the discrete gestures — `on_tap`, `on_double_tap`,
`on_long_press`, `on_swipe`. The continuous ones have their own widgets, because
the event they report is a different one:

| Widget | Handler | Receives |
| --- | --- | --- |
| `PanHandler` | `on_pan` | `PanEvent{dx, dy, vx, vy}` — the drag step and its velocity |
| `ScaleHandler` | `on_scale` · `on_double_tap` | `ScaleEvent{scale, focus_x, focus_y, rotation}` |
| `InteractiveViewer` | `on_interaction` | `ScaleEvent` — one finger pans, two zoom |

```python
from tempest_core import PanEvent, ScaleEvent
from tempest_core import InteractiveViewer, PanHandler


def on_pan(event: PanEvent) -> None:
    """Accumulate the drag — a pan step is relative, not absolute."""

    def mutate(state: Board) -> None:
        state.offset_x += event.dx
        state.offset_y += event.dy

    app.set_state(mutate)


def on_interaction(event: ScaleEvent) -> None:
    """Follow the viewer: the scale zooms, the focus says where."""
    app.set_state(lambda state: setattr(state, "zoom", event.scale))


PanHandler(key="pad", on_pan=on_pan, child=...)
InteractiveViewer(key="map", on_interaction=on_interaction, child=...)
```

Three things decide whether this feels right:

* **`on_pan` is relative.** Each event is the step since the last one, so the app
  accumulates. That is what lets you drag without knowing where the gesture
  started.
* **`on_interaction` receives a `ScaleEvent` even for a plain pan** — one finger
  reports `scale=1` and the focus where the finger is; the app derives the
  translation from the moving focus.
* **The base sheet takes `touch-action` from those three surfaces, and only
  them**: a browser will not send `pointermove` while it is busy scrolling the
  page itself. `GestureDetector` is deliberately left out — tap, swipe and long
  press coexist with scrolling, and taking `touch-action` from it would break
  scrolling on any list that wraps its rows in a detector.

!!! note "A continuous gesture is reported once per frame"
    A `pointermove` arrives 60–120 times a second, and in Mode B each one is a
    round trip. The client reports at most one per frame, keeping the **latest**
    value, and flushes the pending one when the pointer leaves — without that,
    letting go of a 2× pinch left the app at 1.5× (measured in Chrome), because
    the frame that would have carried the last move never came.

## Recap

* `Draggable` + `DragTarget`: drop one thing onto another, with `drag_data`
  arriving as `event.data`.
* `ReorderableList` + `on_reorder`: `from_index` and `to_index`; the move is the
  app's.
* `PageView` + `on_page_change`: native snapping swipe, reported once settled, and
  the app can move `page` back.
* `PanHandler` / `ScaleHandler` / `InteractiveViewer`: drag and pinch, one report
  per frame, with `touch-action` taken from those surfaces only.

Complete examples:
[`examples/reorder_demo`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/reorder_demo/app.py),
[`examples/onboarding-carousel`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/onboarding-carousel/app.py)
and [`examples/kanban-board`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/kanban-board/app.py):

```bash
tempestweb run --mode server --path examples/reorder_demo
```
