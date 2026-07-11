# FAQ Accordion

> 🚀 **What you'll build:** a Frequently Asked Questions page with expandable items (`Accordion`), a single-open policy — opening one item automatically closes the previous one — and a search field that filters entries in real time.

---

## Why this example matters

*Disclosure* patterns (reveal/hide content on demand) appear in every real application: FAQs, help sections, order summaries, settings panels.
`Accordion` encapsulates this behaviour declaratively: you say whether it is open or closed and provide a toggle handler — the framework takes care of the DOM.

In this tutorial you will learn how to:

- Use `Accordion` to reveal and hide content with a click;
- Implement the **single-open** policy (only one item open at a time);
- Filter a list of widgets in real time with `Input`;
- Compose clean layouts with `Card`, `Divider`, `Row`, `Column` and `Text`.

!!! note "Note"
    This example runs **without any modification** in both modes — WASM (Pyodide in the
    browser) and Server (FastAPI + WebSocket). The same Python `view()` serves both.

---

## Prerequisites

Install tempestweb and confirm the CLI is available:

```bash
pip install tempestweb
tempestweb --version
```

---

## Project structure

```
examples/
└── faq-accordion/
    └── app.py
```

Create the folder and file:

```bash
mkdir -p examples/faq-accordion
touch examples/faq-accordion/app.py
```

---

## Step 1 — Imports and FAQ data

Start with all required imports and define the static list of question/answer pairs.

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import Accordion, Card, Divider
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent

_FAQ_ENTRIES: list[tuple[str, str]] = [
    (
        "What is tempestweb?",
        "tempestweb is a framework that lets you build interactive web applications "
        "entirely in typed Python. You declare a widget tree once and the framework "
        "renders it in the browser (Mode A, Pyodide/WASM) or via a FastAPI "
        "WebSocket server (Mode B) — your view function never needs to know "
        "which mode is active.",
    ),
    (
        "Do I need to write any JavaScript?",
        "No. The client-side runtime is a small, zero-dependency JavaScript module "
        "that ships with the framework. Application logic lives exclusively in Python; "
        "the JS layer only handles DOM patching and transport I/O.",
    ),
    (
        "What is the difference between Mode A and Mode B?",
        "Mode A runs Python directly in the browser via Pyodide (WebAssembly). "
        "There is no server round-trip for state changes — everything happens "
        "client-side. Mode B runs Python on a FastAPI server; the browser sends "
        "events over a WebSocket and receives patch sequences back. Mode A is "
        "simpler to deploy (static hosting); Mode B gives full server-side access "
        "to databases and services.",
    ),
    (
        "How do I manage state?",
        "Define a plain Python ``@dataclass`` as your state and pass a fresh "
        "instance to ``make_state()``. Inside your ``view`` function you call "
        "``app.set_state(lambda s: ...)`` to mutate state and trigger a "
        "reconciled rebuild. The framework diffs the old and new widget trees "
        "and sends only the minimal patch sequence to the renderer.",
    ),
    (
        "Can I use third-party Python packages?",
        "In Mode B (server) you can use any Python package as normal. In Mode A "
        "(Pyodide) you are limited to packages that Pyodide ships or that are "
        "pure-Python wheels, because the package must run inside the browser's "
        "WebAssembly sandbox.",
    ),
    (
        "Is TypeScript or a build step required?",
        "No TypeScript and no build step. The client runtime is plain ES-module "
        "JavaScript. You open the app with a single ``<script type='module'>`` "
        "tag — no bundler, no transpiler, no node_modules.",
    ),
    (
        "How does styling work?",
        "Styles are inline, typed Python objects (``Style``, ``Edge``, ``Color``, "
        "etc.). There is no CSS cascade. Each widget carries its own ``Style`` "
        "instance; the renderer serialises it to inline DOM styles. This keeps "
        "styles predictable, refactorable with mypy, and free of selector "
        "specificity surprises.",
    ),
]
```

!!! tip "Tip"
    `_FAQ_ENTRIES` is a module-level constant — a plain list of `(question, answer)`
    tuples. No database, no ORM: the focus of this example is the UI.

**What just happened:**

- The imports bring in exactly what the app uses — nothing unnecessary.
- `_FAQ_ENTRIES` lists the content pairs; state will track which one is open and what text is being searched.

---

## Step 2 — Define state

The state for this app is minimal: which item is open (or `-1` for none) and the text typed in the search field.

```python
@dataclass
class FaqState:
    """State for the FAQ accordion app.

    Attributes:
        open_index: The index of the currently expanded FAQ entry, or ``-1``
            when all items are collapsed.
        query: The current value of the search/filter field.
    """

    open_index: int = -1
    query: str = ""


def make_state() -> FaqState:
    """Build the initial FAQ state with the first entry pre-expanded.

    Returns:
        A fresh :class:`FaqState` with the first accordion open so the page
        renders a non-empty visible body on first mount.
    """
    return FaqState(open_index=0)
```

!!! info "Info"
    Setting `open_index = 0` in `make_state()` means the first question is already
    expanded when the page loads — a better experience than a completely collapsed list.

**What is happening:**

| Field | Type | Role |
|---|---|---|
| `open_index` | `int` | Index of the open `Accordion`; `-1` = all collapsed |
| `query` | `str` | Text typed in the real-time search field |

The **single-open** policy is implemented entirely in `view` logic, not in state: `open_index` holds at most one index at a time.

---

## Step 3 — Event handlers

Before building the widgets, define the two functions that respond to user interactions. They live inside `view` so they have direct access to `app`.

```python
def view(app: App[FaqState]) -> Widget:
    """Render the FAQ accordion page from the current state.

    The page has three regions:

    1. A title heading and a live-search ``Input`` that filters entries.
    2. A ``Column`` of ``Accordion`` items — one per matching FAQ entry.
       A single-open policy means toggling an entry collapses whatever was
       previously open.
    3. A muted footer showing how many entries match the current query.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_search(event: TextChangeEvent) -> None:
        """Update the query and reset the open item when the filter changes.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(s: FaqState) -> None:
            s.query = event.value
            s.open_index = -1

        app.set_state(mutate)

    def toggle(entry_index: int) -> None:
        """Expand the clicked entry or collapse it if it is already open.

        Args:
            entry_index: The index into :data:`_FAQ_ENTRIES` that was toggled.
        """

        def mutate(s: FaqState) -> None:
            s.open_index = -1 if s.open_index == entry_index else entry_index

        app.set_state(mutate)
```

!!! tip "Tip"
    Notice that `on_search` **resets** `open_index` to `-1` every time the user types.
    This prevents a previously-open item from remaining confusingly visible when
    filtering again with a different term.

**Highlights:**

- `app.set_state(mutate)` receives a function that modifies state in place. The framework runs the function, diffs the widget tree, and sends only the necessary patches to the DOM — never a full re-render.
- The single-open policy inside `toggle`: `s.open_index = -1 if s.open_index == entry_index else entry_index`. If the clicked item was already open, it closes; otherwise the new one opens (implicitly closing any other, since `open_index` is a single integer).

---

## Step 4 — Filter visible entries

With state and handlers ready, filter `_FAQ_ENTRIES` based on the current query.

```python
    query_lower = app.state.query.strip().lower()
    visible: list[tuple[int, str, str]] = [
        (idx, question, answer)
        for idx, (question, answer) in enumerate(_FAQ_ENTRIES)
        if not query_lower
        or query_lower in question.lower()
        or query_lower in answer.lower()
    ]
```

!!! info "Info"
    The search checks both the **question** and the **answer** — so the user can type
    a keyword from the content body and find the entry even without knowing the exact title.

**What is happening:**

- `enumerate(_FAQ_ENTRIES)` preserves the original index (`idx`) — important because `toggle(idx)` needs the global index, not the position inside the filtered list.
- `if not query_lower` — when the field is empty, all entries are visible.
- The result is `visible: list[tuple[int, str, str]]` — tuples of `(global_index, question, answer)`.

---

## Step 5 — Build the Accordion items

Iterate over the visible entries and create an `Accordion` for each, with the toggle closure correctly captured.

```python
    accordion_items: list[Widget] = []
    for entry_index, question, answer in visible:
        is_open = app.state.open_index == entry_index

        def make_toggle(i: int = entry_index) -> None:
            """Closure toggling entry ``i``.

            Args:
                i: The FAQ entry index to toggle (default-bound at creation).
            """
            toggle(i)

        accordion_items.append(
            Accordion(
                key=f"faq-{entry_index}",
                title=question,
                open=is_open,
                on_toggle=make_toggle,
                children=[
                    Text(
                        content=answer,
                        key=f"answer-{entry_index}",
                        style=Style(font_size=15.0, line_height=1.6),
                    )
                ],
            )
        )
```

!!! warning "Warning"
    Notice the `def make_toggle(i: int = entry_index)` pattern. In Python, closures
    inside loops capture the **variable**, not the value at the time of iteration. By
    using `i = entry_index` as a default argument, the value is bound at function
    creation time — each `Accordion` gets the correct toggle.

**`Accordion` prop reference:**

| Prop | Type | What it does |
|---|---|---|
| `key` | `str` | Unique identifier for the reconciler |
| `title` | `str` | Text of the clickable header |
| `open` | `bool` | Controls whether the body is expanded (controlled component) |
| `on_toggle` | `callable` | Called when the user clicks the header |
| `children` | `list[Widget]` | Content shown when `open=True` |

---

## Step 6 — Footer counter and empty state

Calculate the counter text and prepare the empty-state message.

```python
    total = len(_FAQ_ENTRIES)
    shown = len(visible)
    if query_lower:
        stripped = app.state.query.strip()
        counter_text = f'{shown} of {total} questions match "{stripped}"'
    else:
        counter_text = f"{total} questions"
```

When no entries match the search, `accordion_items` will be empty. This is handled in the final tree assembly with a feedback message.

---

## Step 7 — Assemble the full tree

Now bring everything together in the widget tree returned by `view`.

```python
    return Column(
        key="faq-root",
        style=Style(
            gap=0.0,
            padding=Edge.symmetric(vertical=24.0, horizontal=20.0),
        ),
        children=[
            # Page heading
            Text(
                content="Frequently Asked Questions",
                key="heading",
                style=Style(font_size=26.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content="Browse the most common questions or search below.",
                key="subtitle",
                style=Style(font_size=14.0, margin=Edge(top=6.0, bottom=20.0)),
            ),
            # Search bar
            Card(
                key="search-card",
                children=[
                    Row(
                        key="search-row",
                        style=Style(gap=8.0),
                        children=[
                            Text(content="Search:", key="search-label"),
                            Input(
                                key="search-input",
                                value=app.state.query,
                                placeholder="Filter questions…",
                                on_change=on_search,
                            ),
                        ],
                    )
                ],
            ),
            # Accordion list (or empty-state message)
            Column(
                key="accordion-list",
                style=Style(gap=8.0, margin=Edge(top=16.0)),
                children=(
                    accordion_items
                    if accordion_items
                    else [
                        Text(
                            content="No questions match your search.",
                            key="empty-msg",
                            style=Style(font_size=14.0),
                        )
                    ]
                ),
            ),
            # Divider + footer
            Divider(
                key="footer-divider",
                style=Style(margin=Edge(top=24.0, bottom=8.0)),
            ),
            Text(
                content=counter_text,
                key="footer-counter",
                style=Style(font_size=12.0),
            ),
        ],
    )
```

**What is happening:**

- The root `Column` uses `Edge.symmetric(vertical=24.0, horizontal=20.0)` for comfortable spacing without having to define each side manually.
- The `Input` is **controlled**: `value=app.state.query` ensures the field always reflects state — there is never a desync between what is on screen and what is in state.
- The ternary expression `accordion_items if accordion_items else [Text(...)]` delivers the empty state declaratively: no extra `if`, no conditional rendering logic outside the tree.
- `Divider` with `style=Style(margin=Edge(top=24.0, bottom=8.0))` visually separates the footer from the main content.

!!! tip "Tip"
    `Edge.symmetric(vertical=v, horizontal=h)` is a `Style` shortcut for
    `top=v, bottom=v, left=h, right=h` in one call. See other shortcuts like
    `Edge.all(n)` and `Edge.only(top=n)` in the
    [Tabbed Profile](./tabs-profile.en.md) example.

---

## Step 8 — The complete file

Here is the complete `app.py`, ready to copy and paste:

```python
"""FAQ Accordion — demonstrates the Disclosure pattern with ``Accordion``.

A realistic FAQ page that manages a list of question/answer pairs and tracks
which entry (if any) is currently expanded.  The app enforces a single-open
policy: opening one item automatically collapses the previously open one,
keeping the page compact and focused.  A search field filters the visible
entries in real time so users can quickly jump to the answer they need.

Like every tempestweb example, this exact ``view`` runs unchanged in both
execution modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import Accordion, Card, Divider
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent

_FAQ_ENTRIES: list[tuple[str, str]] = [
    (
        "What is tempestweb?",
        "tempestweb is a framework that lets you build interactive web applications "
        "entirely in typed Python. You declare a widget tree once and the framework "
        "renders it in the browser (Mode A, Pyodide/WASM) or via a FastAPI "
        "WebSocket server (Mode B) — your view function never needs to know "
        "which mode is active.",
    ),
    (
        "Do I need to write any JavaScript?",
        "No. The client-side runtime is a small, zero-dependency JavaScript module "
        "that ships with the framework. Application logic lives exclusively in Python; "
        "the JS layer only handles DOM patching and transport I/O.",
    ),
    (
        "What is the difference between Mode A and Mode B?",
        "Mode A runs Python directly in the browser via Pyodide (WebAssembly). "
        "There is no server round-trip for state changes — everything happens "
        "client-side. Mode B runs Python on a FastAPI server; the browser sends "
        "events over a WebSocket and receives patch sequences back. Mode A is "
        "simpler to deploy (static hosting); Mode B gives full server-side access "
        "to databases and services.",
    ),
    (
        "How do I manage state?",
        "Define a plain Python ``@dataclass`` as your state and pass a fresh "
        "instance to ``make_state()``. Inside your ``view`` function you call "
        "``app.set_state(lambda s: ...)`` to mutate state and trigger a "
        "reconciled rebuild. The framework diffs the old and new widget trees "
        "and sends only the minimal patch sequence to the renderer.",
    ),
    (
        "Can I use third-party Python packages?",
        "In Mode B (server) you can use any Python package as normal. In Mode A "
        "(Pyodide) you are limited to packages that Pyodide ships or that are "
        "pure-Python wheels, because the package must run inside the browser's "
        "WebAssembly sandbox.",
    ),
    (
        "Is TypeScript or a build step required?",
        "No TypeScript and no build step. The client runtime is plain ES-module "
        "JavaScript. You open the app with a single ``<script type='module'>`` "
        "tag — no bundler, no transpiler, no node_modules.",
    ),
    (
        "How does styling work?",
        "Styles are inline, typed Python objects (``Style``, ``Edge``, ``Color``, "
        "etc.). There is no CSS cascade. Each widget carries its own ``Style`` "
        "instance; the renderer serialises it to inline DOM styles. This keeps "
        "styles predictable, refactorable with mypy, and free of selector "
        "specificity surprises.",
    ),
]


@dataclass
class FaqState:
    """State for the FAQ accordion app.

    Attributes:
        open_index: The index of the currently expanded FAQ entry, or ``-1``
            when all items are collapsed.
        query: The current value of the search/filter field.
    """

    open_index: int = -1
    query: str = ""


def make_state() -> FaqState:
    """Build the initial FAQ state with the first entry pre-expanded.

    Returns:
        A fresh :class:`FaqState` with the first accordion open so the page
        renders a non-empty visible body on first mount.
    """
    return FaqState(open_index=0)


def view(app: App[FaqState]) -> Widget:
    """Render the FAQ accordion page from the current state.

    The page has three regions:

    1. A title heading and a live-search ``Input`` that filters entries.
    2. A ``Column`` of ``Accordion`` items — one per matching FAQ entry.
       A single-open policy means toggling an entry collapses whatever was
       previously open.
    3. A muted footer showing how many entries match the current query.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_search(event: TextChangeEvent) -> None:
        """Update the query and reset the open item when the filter changes.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(s: FaqState) -> None:
            s.query = event.value
            s.open_index = -1

        app.set_state(mutate)

    def toggle(entry_index: int) -> None:
        """Expand the clicked entry or collapse it if it is already open.

        Args:
            entry_index: The index into :data:`_FAQ_ENTRIES` that was toggled.
        """

        def mutate(s: FaqState) -> None:
            s.open_index = -1 if s.open_index == entry_index else entry_index

        app.set_state(mutate)

    query_lower = app.state.query.strip().lower()
    visible: list[tuple[int, str, str]] = [
        (idx, question, answer)
        for idx, (question, answer) in enumerate(_FAQ_ENTRIES)
        if not query_lower
        or query_lower in question.lower()
        or query_lower in answer.lower()
    ]

    accordion_items: list[Widget] = []
    for entry_index, question, answer in visible:
        is_open = app.state.open_index == entry_index

        def make_toggle(i: int = entry_index) -> None:
            """Closure toggling entry ``i``.

            Args:
                i: The FAQ entry index to toggle (default-bound at creation).
            """
            toggle(i)

        accordion_items.append(
            Accordion(
                key=f"faq-{entry_index}",
                title=question,
                open=is_open,
                on_toggle=make_toggle,
                children=[
                    Text(
                        content=answer,
                        key=f"answer-{entry_index}",
                        style=Style(font_size=15.0, line_height=1.6),
                    )
                ],
            )
        )

    total = len(_FAQ_ENTRIES)
    shown = len(visible)
    if query_lower:
        stripped = app.state.query.strip()
        counter_text = f'{shown} of {total} questions match "{stripped}"'
    else:
        counter_text = f"{total} questions"

    return Column(
        key="faq-root",
        style=Style(
            gap=0.0,
            padding=Edge.symmetric(vertical=24.0, horizontal=20.0),
        ),
        children=[
            Text(
                content="Frequently Asked Questions",
                key="heading",
                style=Style(font_size=26.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content="Browse the most common questions or search below.",
                key="subtitle",
                style=Style(font_size=14.0, margin=Edge(top=6.0, bottom=20.0)),
            ),
            Card(
                key="search-card",
                children=[
                    Row(
                        key="search-row",
                        style=Style(gap=8.0),
                        children=[
                            Text(content="Search:", key="search-label"),
                            Input(
                                key="search-input",
                                value=app.state.query,
                                placeholder="Filter questions…",
                                on_change=on_search,
                            ),
                        ],
                    )
                ],
            ),
            Column(
                key="accordion-list",
                style=Style(gap=8.0, margin=Edge(top=16.0)),
                children=(
                    accordion_items
                    if accordion_items
                    else [
                        Text(
                            content="No questions match your search.",
                            key="empty-msg",
                            style=Style(font_size=14.0),
                        )
                    ]
                ),
            ),
            Divider(
                key="footer-divider",
                style=Style(margin=Edge(top=24.0, bottom=8.0)),
            ),
            Text(
                content=counter_text,
                key="footer-counter",
                style=Style(font_size=12.0),
            ),
        ],
    )
```

---

## Step 9 — Run the app

Run in **Mode A** (Python in the browser via Pyodide/WASM):

```bash
tempestweb dev --mode wasm examples/faq-accordion/app.py
```

Run in **Mode B** (Python on the server via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/faq-accordion/app.py
```

Open `http://localhost:8000` in your browser. You should see:

- ✅ "Frequently Asked Questions" title prominent at the top;
- ✅ Subtitle and search field inside a `Card`;
- ✅ First question already expanded on load (thanks to `make_state(open_index=0)`);
- ✅ Clicking any question expands it and collapses the previously open one;
- ✅ Clicking an already-open question collapses it;
- ✅ Typing in the search field filters items in real time;
- ✅ When no entries match, "No questions match your search." appears;
- ✅ The footer shows the total count or how many entries match the current search.

!!! check "Full quality check"
    To verify the code passes all quality gates:

    ```bash
    ruff check examples/faq-accordion/app.py
    ruff format --check examples/faq-accordion/app.py
    mypy examples/faq-accordion/app.py
    ```

    All three should exit with code 0.

---

## Recap

In this tutorial you built a complete FAQ page with live filtering and learned:

- 💡 **`Accordion`** is a *controlled component*: `open=bool` and `on_toggle=callable` are all you need. State lives in your `@dataclass`, not inside the widget.
- 💡 The **single-open policy** fits in one line: `s.open_index = -1 if s.open_index == entry_index else entry_index`. No special framework logic required.
- 💡 **Closures in loops** require the `def f(i: int = entry_index)` pattern to capture the correct value at each iteration — a classic Python gotcha.
- 💡 A **controlled `Input`** (`value=app.state.query`) ensures the field never gets out of sync with state — essential for live filters.
- 💡 **`Card` + `Row` + `Divider`** compose a clean layout without a single line of manual CSS.
- 💡 The same `app.py` runs in both modes — WASM and Server — without any modification.

---

## Next steps

- Read the [core tutorial](../tutorial/index.md) to understand the full tempestweb lifecycle.
- Explore the tab navigation pattern in the [Tabbed Profile](./tabs-profile.en.md) example.
- Add open/close animations to `Accordion` with `AnimatedSwitcher` (coming soon).
