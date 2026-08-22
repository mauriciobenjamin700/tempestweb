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
from tempest_core.widgets.events import DragEvent
from tempest_core.widgets.gestures import Draggable, DragTarget


def view(app: App[Board]) -> Widget:
    """Render a card that can be dropped into a column."""

    def dropped(event: DragEvent) -> None:
        app.set_state(lambda state: state.move(event.data, to="done"))

    return DragTarget(
        key="done",
        on_drop=dropped,
        children=[
            Draggable(
                key="card-7",
                drag_data="card-7",
                children=[Text(content="Write the post")],
            )
        ],
    )
```

`drag_data` is what arrives as `event.data` in `on_drop` — usually the id of what
was dragged. `on_drag` tells you the drag started, if you want to paint a
"carrying this" state.

## Reordering a list

`ReorderableList` is the case where the item does not go *somewhere else*: it
changes position within its own list. The handler receives both positions — and
moving is the app's job, because the order is state:

```python
from tempest_core import App, Container, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import ReorderEvent
from tempest_core.widgets.gestures import ReorderableList


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
from tempest_core.widgets.events import PageChangeEvent
from tempest_core.widgets.layout import PageView


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

## Recap

* `Draggable` + `DragTarget`: drop one thing onto another, with `drag_data`
  arriving as `event.data`.
* `ReorderableList` + `on_reorder`: `from_index` and `to_index`; the move is the
  app's.
* `PageView` + `on_page_change`: native snapping swipe, reported once settled, and
  the app can move `page` back.

Complete examples:
[`examples/reorder_demo`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/reorder_demo/app.py),
[`examples/onboarding-carousel`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/onboarding-carousel/app.py)
and [`examples/kanban-board`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/kanban-board/app.py):

```bash
tempestweb run --mode server --path examples/reorder_demo
```
