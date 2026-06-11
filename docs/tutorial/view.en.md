# 1. The view tree

The basic unit of tempestweb is the `view()` function. It receives the **app**
(which exposes the current state) and returns a **widget tree**. No JSX, no
template — just plain, typed Python.

## The `view` function

```python
from tempestweb._core import App, Column, Style, Text, Widget
from tempestweb._core.style import Edge


def view(app: App[CounterState]) -> Widget:  # (1)!
    """Render the counter UI from the current state."""
    return Column(  # (2)!
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),  # (3)!
        ],
    )
```

1. `view` receives `App[CounterState]` — the typed state handle — and **always**
   returns a `Widget`. Input and output types are part of the contract.
2. `Column` is a vertical flex container. `Row` is the horizontal one. Both take
   `style` and `children`.
3. `Text` shows text. `app.state.value` reads the current state — the view is a
   **function of state**.

!!! note "The view is pure"
    `view()` **mutates nothing**. It reads `app.state` and describes the UI that
    matches that state. Changing the state is the handlers' job (next page) — the
    view only draws.

## The counter's widgets

The counter uses four widget types, all from the core:

| Widget | What it is | Main props |
|---|---|---|
| `Column` | Vertical flex container | `style`, `children` |
| `Row` | Horizontal flex container | `style`, `children` |
| `Text` | Text | `content`, `style`, `key` |
| `Button` | Clickable button | `label`, `on_click`, `style`, `key` |

## The `key`: stable identity

Notice `key="label"`. The `key` gives the widget a **stable identity** across
rebuilds. When the state changes and the view runs again, the reconciler uses the
`key` to match the new widget with the old one — so it can emit a minimal patch
(change only the text) instead of recreating the node.

```python
Text(content=f"Count: {app.state.value}", key="label")
```

!!! tip "When to give a `key`"
    Give a `key` to any widget that **persists across rebuilds** and whose content
    changes (the count text, the buttons). Dynamic list items also want a stable
    `key`. Without a `key`, reconciliation falls back to positional matching.

## Style is a typed object

`Style` is a Pydantic object — not a CSS string. You declare intent and the
client translates it to CSS:

```python
Style(gap=8.0, padding=Edge.all(16))  # gap: 8px; padding: 16px;
```

- `gap=8.0` → `gap: 8px` on the flex container.
- `Edge.all(16)` → `padding: 16px 16px 16px 16px`.

!!! info "Style → CSS is almost identity"
    `Style` was designed by copying the CSS vocabulary (flexbox, box model,
    typography). The translation lives in the client (`client/style.js`) and is
    shared by both modes. Full detail in the [wire contract](../wire-contract.md).

## The complete counter tree

Putting container, text and buttons together:

```python
from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import Edge


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", key="dec"),  # on_click comes on page 2
                    Button(label="+", key="inc"),
                ],
            ),
        ],
    )
```

This produces the tree (IR) that the reconciler serializes to the client — the
exact format is pinned in
[`tests/fixtures/node_initial.json`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/tests/fixtures/node_initial.json).

## Recap

- `view(app) -> Widget` is a **pure function of state**.
- Widgets (`Column`, `Row`, `Text`, `Button`) are typed core objects.
- `key` gives **stable identity** so reconciliation emits minimal patches.
- `Style` is a typed object that becomes CSS in the client.

Now the buttons need to **do something**. Let's move on to
[state and handlers](state.md). 🚀
