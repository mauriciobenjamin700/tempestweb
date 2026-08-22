# Long lists

A list of 10,000 items cannot become 10,000 DOM nodes. tempestweb solves that
with **virtualized lists**: you declare *how many* items exist and *how* to build
the item at an index, and only the visible window is ever materialized.

On this page you build a virtualized list, then wire **infinite scroll** and
**pull-to-refresh** — the two edges of any real list. 🚀

## Virtualization: `LazyColumn`

Start with the simplest case: a thousand items, one window.

```python
from tempest_core import App, Container, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.lists import LazyColumn


def view(app: App[None]) -> Widget:
    """Render a thousand items with only a window in the DOM."""

    def build_row(index: int) -> Widget:
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    return LazyColumn(
        key="rows",
        item_count=1000,
        item_builder=build_row,
        window_size=30,
        style=Style(height=300.0),
    )
```

Piece by piece:

* **`item_count=1000`** — the size of the whole list. This is what the scrollbar
  describes.
* **`item_builder=build_row`** — the factory that builds the item at an index. It
  is a Python callable: it never crosses the wire, and it is only called for the
  indices in the window.
* **`window_size=30`** — how many items are materialized. Ask for more than fits
  the viewport, so there is slack before the window has to slide.
* **`style=Style(height=300.0)`** — the height is what turns the element into a
  scrollable viewport. With no height the list grows with its content and never
  scrolls.

!!! tip "Every item needs a `key`"
    Items are keyed by their absolute index, so a sliding window becomes a
    minimal remove/reorder/insert sequence instead of a brand-new tree.

The result in the browser: **30 nodes** in the DOM and a scrollbar for a thousand
items — the off-window space is reserved without creating a single element.

## Infinite scroll: `on_end_reached`

A paginated list does not know its final size: it loads more when the reader gets
close to the end. Declare `on_end_reached`.

```python
from dataclasses import dataclass

from tempest_core import App, Container, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets.events import EndReachedEvent
from tempest_core.widgets.lists import LazyColumn

PAGE_SIZE = 25
TOTAL_ITEMS = 200


@dataclass
class ListState:
    """How many items are available so far."""

    loaded: int = PAGE_SIZE


def view(app: App[ListState]) -> Widget:
    """Render a list that loads another page at its end."""

    def build_row(index: int) -> Widget:
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    def load_more(event: EndReachedEvent) -> None:
        if app.state.loaded >= TOTAL_ITEMS:
            return
        app.set_state(
            lambda state: setattr(
                state, "loaded", min(TOTAL_ITEMS, state.loaded + PAGE_SIZE)
            )
        )

    return LazyColumn(
        key="rows",
        item_count=app.state.loaded,
        item_builder=build_row,
        window_size=30,
        end_reached_threshold=0.8,
        on_end_reached=load_more,
        style=Style(height=300.0),
    )
```

`end_reached_threshold` is the fraction of the scroll that fires the event —
`0.8`, the default, means "80% of the way there". The client reports
`end_reached` **once per crossing**: it entered the end zone, it said so, and it
only says so again after the list leaves that zone (which is what happens on its
own once the handler appends items).

!!! warning "Always have a stopping condition"
    The event keeps being reported while the reader scrolls at the end of the
    list. If the handler grows the state without a bound, the list grows forever.
    The `return` once everything is loaded is what makes that harmless —
    answering with an unchanged state is a perfectly valid answer.

## Pull-to-refresh: `on_refresh` + `refreshing`

The DOM has no per-element pull-to-refresh, so the client recognizes the gesture:
a drag **from the scroll origin**, along the list's axis, past 64px. Away from
the origin, a drag is a scroll, not a pull.

```python
import asyncio

from tempest_core.widgets.events import RefreshEvent


async def reload(event: RefreshEvent) -> None:
    """Reload the list from the top."""
    app.set_state(lambda state: setattr(state, "refreshing", True))
    await asyncio.sleep(0.6)  # the real fetch goes here

    def done(state: ListState) -> None:
        state.refreshing = False
        state.loaded = PAGE_SIZE

    app.set_state(done)
```

Pass the handler **and** the state to the list:

```python
LazyColumn(
    key="rows",
    item_count=app.state.loaded,
    item_builder=build_row,
    refreshing=app.state.refreshing,
    on_refresh=reload,
    on_end_reached=load_more,
    style=Style(height=300.0),
)
```

`refreshing` does two things: it draws the indicator (a band at the pull edge)
and it **blocks a second pull** while the reload is in flight. It also becomes
`aria-busy`, so the wait is announced.

!!! note "An async handler is what makes the state visible"
    A sync handler turns `refreshing` on and off within the same tick — the
    reader never sees the indicator. `async` plus an awaited fetch renders the
    intermediate state.

### `RefreshControl`: the gesture without a list

Want pull-to-refresh on content that is not a list? Use the standalone control:

```python
from tempest_core.widgets.lists import RefreshControl

RefreshControl(key="pull", refreshing=app.state.refreshing, on_refresh=reload)
```

It is an IR leaf: the renderer owns what shows inside it — a spinner that is
invisible at rest, visible once the pull arms, and spinning while `refreshing` is
set.

## `SectionList`: the list that flows in the page

`SectionList` groups sections with a header and per-section virtualized items. It
is not a viewport with its own height: it flows in the page. `on_end_reached`
works the same way — progress is measured by how much of the list's box the
page's viewport has revealed.

??? info "Technical details: how the client measures the end"
    The renderer marks the list with `data-tw-end-threshold`, and the client
    (`client/lists.js`) picks the geometry:

    * an element that scrolls its own box →
      `(scrollTop + clientHeight) / scrollHeight`, which for a virtualized list
      already includes the reserved off-window space, and therefore tracks the
      real `item_count`;
    * an element in page flow → how much of its box the viewport revealed.

    The pull gesture becomes `data-tw-refresh` (`y`/`x`, so on a `LazyRow` the
    pull is to the right) and the armed state becomes `data-tw-pull-armed`. On
    the wire both events are `{"type": "end_reached", "key": "..."}` and
    `{"type": "refresh", "key": "..."}` — no payload, identical in all three
    modes.

## Recap

* `LazyColumn` / `LazyRow` / `LazyGrid` declare `item_count` + `item_builder`;
  only the window exists in the DOM. The height in `Style` is what makes the
  viewport scroll.
* `on_end_reached` + `end_reached_threshold` give you infinite scroll — with a
  stopping condition in the handler.
* `on_refresh` + `refreshing` give you pull-to-refresh, with an indicator and no
  duplicated reload. Make the handler `async` so the state is visible.
* `RefreshControl` takes the gesture to content that is not a list.
* `SectionList` measures its end from the page scroll, not from its own.

The complete example, with all three wired at once, lives in
[`examples/list_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/list_demo/app.py):

```bash
tempestweb run --mode server --path examples/list_demo
```
