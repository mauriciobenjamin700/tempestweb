# Tutorial — the Counter

Welcome! 👋 In this tutorial you build the **counter**, tempestweb's canonical
app, from scratch. It is a `+` button, a `-` button and a text showing the
count. Simple — but it exercises the **entire wire contract**: the view tree,
state, handlers, patches and the three execution modes.

We go one concept per page, in order:

<div class="grid cards" markdown>

-   __[1. The view tree](view.md)__

    ---

    How to write `view()` and assemble typed widgets (`Column`, `Row`, `Text`,
    `Button`).

-   __[2. State and handlers](state.md)__

    ---

    `set_state`, the coalesced rebuild, and why handlers never touch the DOM.

-   __[3. Patches on the wire](patches.md)__

    ---

    What the reconciler emits when the count changes — and how the client applies
    it.

-   __[4. Running the modes](modes.md)__

    ---

    The same `app.py` under `--mode wasm`, `--mode server` and `--mode transpile`,
    without changing a line.

</div>

!!! tip "Prerequisite"
    You only need to have done the [Installation](../installation.md). Each page
    assumes only the previous one — start on page one and keep going.

!!! note "Just want to run it, not type it?"
    `tempestweb new <name>` scaffolds exactly this counter (with `tempestweb.toml`)
    as a runnable project — see
    [Create your first project](../installation.md#create-your-first-project).
    This tutorial rebuilds the same app from scratch to explain every piece.

## What we will build

By the end, this is the complete app — exactly what lives in
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/counter/app.py):

```python
"""Counter — the canonical tempestweb example."""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

!!! check "Everything you need to know is here"
    There is no hidden magic. The next four pages explain every line above, piece
    by piece. Let's start with the [view tree](view.md). 🚀
