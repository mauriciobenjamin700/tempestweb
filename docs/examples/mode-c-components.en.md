# Mode C Component Gallery — Zero Python in the Browser ⚡

A transpiled app exercising **every ported component** of `tempest_core`:
surfaces, bars, content rows, feedback blocks and the interactive ones. No Python
runs in the browser — and the tree is the same one Modes A and B build.

---

## What you will build

A gallery in sections, one per component family:

| Section | Components |
|---|---|
| **Surfaces** | `Surface`, `Card`, `Sidebar`, `Drawer`, `Grid`, `StyledContainer` |
| **Bars** | `Header`, `AppBar`, `NavBar`, `Breadcrumb`, `Footer`, `Burger` |
| **Content** | `ListTile`, `Avatar`, `Tag`, `Chip`, `Badge`, `Divider` |
| **Feedback** | `Alert`, `Banner`, `EmptyState`, `Stat`, `ProgressStepper`, `ConfidenceBadge` |
| **Interactive** | `Rating`, `Stepper`, `SearchBar`, `SegmentedControl`, `RadioGroup` |

!!! tip "Why this example exists"
    It is the artifact that proves the Mode C port. Each component's composition is
    **rewritten by hand** in `client/transpile/components.js` (the core's
    `render()` cannot run without Python) and its style comes from a table
    generated from the core. A gallery that renders identically in all three modes
    is the evidence that the rewrite stayed faithful.

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading: [Ready-made components](../tutorial/components.md) and
[Mode C — transpile](../advanced/transpile.md).

---

## Running it

```bash
# a static bundle: index.html + the client + the transpiled app. Zero Python.
tempestweb build --mode transpile --path examples/mode-c-components

# development with livereload (recompiles on every save)
tempestweb dev --mode transpile --path examples/mode-c-components --port 8000
```

The same `app.py` runs in the other two modes unchanged:

```bash
tempestweb run --mode server --path examples/mode-c-components --port 8000
tempestweb run --mode wasm   --path examples/mode-c-components --port 8000
```

---

## The rule this example teaches: give every component a `key`

```python
from tempest_core import Card, Column, Text, Widget


def two_cards() -> Widget:
    """Two sibling surfaces, each with its own key."""
    return Column(
        key="cards",
        children=[
            Card(key="card-left", children=[Text(content="left", key="left-label")]),
            Card(key="card-right", children=[Text(content="right", key="right-label")]),
        ],
    )
```

!!! warning "Without a `key`, two identical components fight over one name"
    A component's default key is its **own name**: two `Card`s under the same
    parent would both answer to `card`. The reconciler addresses children by key
    and the event router matches by key — so two unkeyed instances trade patches
    and events with each other. Every instance in this example carries an explicit
    `key` for that reason.

!!! note "A child's key is derived from its parent's"
    Since `tempest-core` 0.15.0 each component derives the keys of the children it
    creates from its own (`faq-3` → `faq-3-item-0`), so two instances on one screen
    no longer collide on their children. The parent's `key` is still yours to give.

---

## What stays out of Mode C

A component whose **tree depends on its data** has no fixed composition to port
without compiling the core's `render()`: `DataTable`/`Table`, `Tabs`, `Accordion`,
the charts, `DetectionOverlay`, `ResultView`, `Calendar`/`Clock`, the pickers and
`CollapsingAppBar`. Tracked in
[#107](https://github.com/mauriciobenjamin700/tempestweb/issues/107) — all of them
work in Modes A and B.

---

## Recap

* Mode C delivers the ported components with the **same tree** as Modes A and B,
  pinned by a parity matrix derived from the core.
* The composition is hand-rewritten; the style comes from a generated table. That
  is why this gallery exists: it is the visual proof of the port.
* Give every component an explicit `key` — the default is the class name.
* A data-driven component waits (#107), and only in Mode C.
