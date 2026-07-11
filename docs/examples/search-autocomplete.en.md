# Search with Autocomplete

Build a **live country-search widget**: as the user types, the `Autocomplete`
widget narrows suggestions in real time; `Chip` pills let the user restrict
results by continent before typing a single character. 🔍

By the end of this tutorial you will have a complete app that exercises
`Autocomplete`, `Chip`, `Wrap`, `Column`, `Row`, `Text` and `Button` — with
two typed handlers (`on_change` and `on_select`) and derived state that is
recomputed on every interaction.

---

## The problem

Autocomplete search boxes are ubiquitous, but implementing them correctly
involves three simultaneous challenges:

1. **Live filtering** — the suggestion list changes with every keystroke.
2. **Selection vs. typing** — confirming a suggestion is different from
   continuing to type; the state must distinguish the two.
3. **Category filtering** — the user wants to restrict the universe of results
   *before* typing, using clickable pills.

tempestweb solves all of this with explicit state and two typed events:
`TextChangeEvent` (each keystroke) and `SelectEvent` (item chosen).

!!! note "What you will practice"
    - `Autocomplete` — text field with a dynamic suggestion list.
    - `Chip` — clickable pill with a `selected` state for category filters.
    - `Wrap` — layout that reflows pills automatically when space runs out.
    - `TextChangeEvent` and `SelectEvent` — the two typed events from `Autocomplete`.
    - Derived state with `recompute()` — suggestions recalculated whenever query or category changes.
    - Closures in category handlers — `_make_chip` captures the right `cat` for each pill.

---

## Prerequisites

Before continuing, make sure you have completed the
[Installation](../installation.md) and read the
[Counter Tutorial](../tutorial/index.md) — this example assumes you already know
`Column`, `Row`, `Text`, `App`, `make_state`, `view`, and the `set_state` rebuild
cycle.

---

## The complete app

This is the exact code from
[`examples/search-autocomplete/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/search-autocomplete/app.py).
Copy it, run it, then read the explanation piece by piece.

```python
"""Search with autocomplete — exercises Autocomplete, Chip, and dynamic filtering.

A realistic country-search widget: as the user types, the
:class:`~tempest_core.widgets.Autocomplete` widget narrows the suggestion
list in real time. Selecting a suggestion commits it as the active choice and
shows it as a :class:`~tempest_core.components.Chip` below the field. The
user can clear the committed choice with a button and start over.

The demo also showcases *category filtering*: three
:class:`~tempest_core.components.Chip` pills let the user restrict suggestions
to a continent (All / Americas / Europe), so the autocomplete's ``options``
list changes whenever the query *or* the category filter changes.

Run in either mode — the ``view`` function is transport-agnostic::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import Chip
from tempest_core.style import Edge
from tempest_core.widgets import (
    Autocomplete,
    Button,
    Column,
    Row,
    Text,
    Wrap,
)
from tempest_core.widgets.events import SelectEvent, TextChangeEvent

# ---------------------------------------------------------------------------
# Data catalog
# ---------------------------------------------------------------------------

_COUNTRIES: list[tuple[str, str]] = [
    ("Argentina", "Americas"),
    ("Bolivia", "Americas"),
    ("Brazil", "Americas"),
    ("Canada", "Americas"),
    ("Chile", "Americas"),
    ("Colombia", "Americas"),
    ("Ecuador", "Americas"),
    ("Mexico", "Americas"),
    ("Paraguay", "Americas"),
    ("Peru", "Americas"),
    ("United States", "Americas"),
    ("Uruguay", "Americas"),
    ("Venezuela", "Americas"),
    ("Austria", "Europe"),
    ("Belgium", "Europe"),
    ("Czech Republic", "Europe"),
    ("Denmark", "Europe"),
    ("Finland", "Europe"),
    ("France", "Europe"),
    ("Germany", "Europe"),
    ("Greece", "Europe"),
    ("Hungary", "Europe"),
    ("Ireland", "Europe"),
    ("Italy", "Europe"),
    ("Netherlands", "Europe"),
    ("Norway", "Europe"),
    ("Poland", "Europe"),
    ("Portugal", "Europe"),
    ("Romania", "Europe"),
    ("Spain", "Europe"),
    ("Sweden", "Europe"),
    ("Switzerland", "Europe"),
    ("United Kingdom", "Europe"),
]

_CATEGORIES: list[str] = ["All", "Americas", "Europe"]

_MAX_SUGGESTIONS: int = 8


def _filter_suggestions(query: str, category: str) -> list[str]:
    """Return up to ``_MAX_SUGGESTIONS`` country names matching the current query.

    Matching is case-insensitive and substring-based so partial strings like
    ``"bra"`` find ``"Brazil"`` immediately. The ``category`` filter limits the
    pool to a single continent when it is not ``"All"``.

    Args:
        query: The current text typed into the search field.
        category: The active category filter — ``"All"`` disables the filter.

    Returns:
        A list of at most :data:`_MAX_SUGGESTIONS` matching country names in
        alphabetical order.
    """
    q = query.strip().lower()
    matches: list[str] = []
    for name, continent in _COUNTRIES:
        if category != "All" and continent != category:
            continue
        if not q or q in name.lower():
            matches.append(name)
    return sorted(matches)[:_MAX_SUGGESTIONS]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SearchState:
    """State for the search-autocomplete example.

    Attributes:
        query: The live text in the autocomplete field.
        category: The active continent filter.
        committed: The country name that was explicitly selected, or ``""``
            when nothing has been confirmed yet.
        suggestions: The current filtered suggestion list derived from
            ``query`` and ``category``; recomputed on every relevant mutation.
    """

    query: str = ""
    category: str = "All"
    committed: str = ""
    suggestions: list[str] = field(default_factory=list)

    def recompute(self) -> None:
        """Refresh :attr:`suggestions` from the current query and category.

        Called internally after every mutation that changes the filter state.
        """
        self.suggestions = _filter_suggestions(self.query, self.category)


def make_state() -> SearchState:
    """Build the initial state with a full suggestion list.

    Returns:
        A fresh :class:`SearchState` with all countries visible and no active
        query or selection.
    """
    s = SearchState()
    s.recompute()
    return s


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[SearchState]) -> Widget:
    """Render the search-autocomplete UI from the current state.

    The view is a vertical column with three sections:

    1. **Category filter** — three :class:`Chip` pills to narrow by continent.
    2. **Autocomplete field** — the live-filtered text field.
    3. **Result area** — either a confirmation card for the committed country
       or a placeholder prompt.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    s: SearchState = app.state

    # -- handlers ----------------------------------------------------------

    def on_query_change(event: TextChangeEvent) -> None:
        """Update the live query and refresh suggestions on each keystroke.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(st: SearchState) -> None:
            st.query = event.value
            st.committed = ""
            st.recompute()

        app.set_state(mutate)

    def on_suggestion_select(event: SelectEvent) -> None:
        """Commit the selected suggestion and clear the live query.

        Args:
            event: The select event carrying the chosen suggestion value.
        """

        def mutate(st: SearchState) -> None:
            st.committed = event.value
            st.query = event.value
            st.suggestions = []

        app.set_state(mutate)

    def on_clear() -> None:
        """Reset the query, committed selection and suggestions."""

        def mutate(st: SearchState) -> None:
            st.query = ""
            st.committed = ""
            st.recompute()

        app.set_state(mutate)

    def on_category(cat: str) -> None:
        """Switch the active category filter and refresh suggestions.

        Args:
            cat: The category label to activate.
        """

        def mutate(st: SearchState) -> None:
            st.category = cat
            st.committed = ""
            st.query = ""
            st.recompute()

        app.set_state(mutate)

    # -- category chips ----------------------------------------------------

    def _make_chip(cat: str) -> Widget:
        """Build one category-filter chip for ``cat``.

        Args:
            cat: The category label this chip represents.

        Returns:
            A :class:`Chip` widget bound to ``on_category``.
        """

        def click() -> None:
            on_category(cat)

        return Chip(
            key=f"cat-{cat}",
            label=cat,
            selected=(s.category == cat),
            on_click=click,
        )

    category_chips: list[Widget] = [_make_chip(cat) for cat in _CATEGORIES]

    # -- result area -------------------------------------------------------

    if s.committed:
        result_children: list[Widget] = [
            Text(
                key="chosen-label",
                content="Selected country:",
                style=Style(font_size=13.0),
            ),
            Row(
                key="chosen-row",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="chosen-value",
                        content=s.committed,
                        style=Style(font_size=18.0),
                    ),
                    Button(
                        key="clear-btn",
                        label="Clear",
                        on_click=on_clear,
                        style=Style(
                            padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                            radius=6.0,
                        ),
                    ),
                ],
            ),
        ]
    else:
        result_children = [
            Text(
                key="prompt",
                content="Type a country name or pick one from the suggestions.",
                style=Style(font_size=14.0),
            ),
        ]

    # -- root layout -------------------------------------------------------

    return Column(
        key="root",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=[
            Text(
                key="heading",
                content="Country Search",
                style=Style(font_size=22.0),
            ),
            Text(
                key="subheading",
                content="Filter by continent, then search:",
                style=Style(font_size=14.0),
            ),
            Wrap(
                key="categories",
                style=Style(gap=8.0),
                children=category_chips,
            ),
            Autocomplete(
                key="search",
                value=s.query,
                placeholder="e.g. Brazil, France…",
                options=s.suggestions,
                on_change=on_query_change,
                on_select=on_suggestion_select,
            ),
            Column(
                key="result",
                style=Style(gap=8.0, padding=Edge.all(12.0), radius=10.0),
                children=result_children,
            ),
        ],
    )
```

---

## Explaining piece by piece

### 1. The data catalog

```python
_COUNTRIES: list[tuple[str, str]] = [
    ("Argentina", "Americas"),
    ("Brazil", "Americas"),
    ("France", "Europe"),
    # ...
]

_CATEGORIES: list[str] = ["All", "Americas", "Europe"]

_MAX_SUGGESTIONS: int = 8
```

The data lives outside any class — these are module-level constants, immutable.
`_COUNTRIES` is a list of `(name, continent)` tuples. `_MAX_SUGGESTIONS` ensures
the suggestion list never grows unbounded and makes the DOM heavy.

!!! tip "Tip"
    In a real app you would fetch this data from an API or a database.
    `_filter_suggestions` would be `async` and call a repository. The structure
    of `view` and state stays identical — only the origin of the data changes.

---

### 2. The pure filtering function

```python
def _filter_suggestions(query: str, category: str) -> list[str]:
    q = query.strip().lower()
    matches: list[str] = []
    for name, continent in _COUNTRIES:
        if category != "All" and continent != category:
            continue
        if not q or q in name.lower():
            matches.append(name)
    return sorted(matches)[:_MAX_SUGGESTIONS]
```

Two criteria combined:

- **Continent:** when `category != "All"`, countries from other continents are
  skipped.
- **Query:** `q in name.lower()` matches substrings case-insensitively.
  `"bra"` finds `"Brazil"`. When `q` is empty, all countries in the continent
  appear.

The result is sorted alphabetically and capped at `_MAX_SUGGESTIONS`.

!!! note "Note"
    The function knows nothing about `SearchState` or `App` — it is completely
    pure and testable in isolation with `pytest`.

---

### 3. State with `recompute()`

```python
@dataclass
class SearchState:
    query: str = ""
    category: str = "All"
    committed: str = ""
    suggestions: list[str] = field(default_factory=list)

    def recompute(self) -> None:
        self.suggestions = _filter_suggestions(self.query, self.category)
```

`suggestions` is **derived state**: always calculated from `query` and
`category`. Instead of recalculating in each handler separately, `recompute()`
centralises that logic. Any handler that changes `query` or `category` calls
`recompute()` before ending the mutation.

!!! info "Derived vs. independent state"
    `query`, `category` and `committed` are **independent** — the user controls
    them directly. `suggestions` is **derived** — it should never be mutated
    directly; always go through `recompute()`. This pattern prevents
    inconsistencies where `suggestions` and `query` fall out of sync.

`make_state()` calls `recompute()` immediately, so when the app opens the field
already displays suggestions (all countries, no filter).

---

### 4. Two distinct events: `on_change` vs. `on_select`

`Autocomplete` exposes two handlers with different semantics:

```python
Autocomplete(
    key="search",
    value=s.query,
    placeholder="e.g. Brazil, France…",
    options=s.suggestions,
    on_change=on_query_change,
    on_select=on_suggestion_select,
)
```

| Handler | Event | Fires when |
|---|---|---|
| `on_change` | `TextChangeEvent` | On each keystroke in the field |
| `on_select` | `SelectEvent` | When the user clicks a suggestion |

#### `on_change` handler — each keystroke

```python
def on_query_change(event: TextChangeEvent) -> None:
    def mutate(st: SearchState) -> None:
        st.query = event.value
        st.committed = ""
        st.recompute()

    app.set_state(mutate)
```

Three things happen atomically:

1. `st.query` receives the current text in the field.
2. `st.committed` is cleared — the user resumed typing, so the previous
   selection is no longer valid.
3. `st.recompute()` recalculates suggestions for the new `query`.

#### `on_select` handler — suggestion selection

```python
def on_suggestion_select(event: SelectEvent) -> None:
    def mutate(st: SearchState) -> None:
        st.committed = event.value
        st.query = event.value
        st.suggestions = []

    app.set_state(mutate)
```

The opposite behaviour: the suggestion list is **cleared** (nothing more to
show) and `committed` receives the chosen value. `query` also receives the value
so the text field displays the selected country name.

!!! tip "Tip"
    `SelectEvent.value` carries exactly the item from the `options` list that
    the user clicked — no index lookup or manual mapping needed.

---

### 5. Category chips with closures

```python
def _make_chip(cat: str) -> Widget:
    def click() -> None:
        on_category(cat)

    return Chip(
        key=f"cat-{cat}",
        label=cat,
        selected=(s.category == cat),
        on_click=click,
    )

category_chips: list[Widget] = [_make_chip(cat) for cat in _CATEGORIES]
```

`_make_chip` creates one chip per category. The critical point is using a
**factory function** instead of a direct lambda in the `for` loop. If you wrote:

```python
# ❌ Classic closure-in-loop trap
for cat in _CATEGORIES:
    Chip(on_click=lambda: on_category(cat), ...)
```

all lambdas would capture the **same** `cat` variable from the loop — when
clicked, every one would fire with the loop's final value (`"Europe"`).
`_make_chip` solves this because each call creates a **new scope** with its
own `cat`.

`selected=(s.category == cat)` renders the chip as visually active when it
matches the current state category.

!!! warning "Warning"
    This pattern — a factory to capture a loop variable — is required whenever
    you create widgets with handlers inside a `for`. A direct lambda in the loop
    is a classic Python closure trap.

---

### 6. Conditional result area

```python
if s.committed:
    result_children: list[Widget] = [
        Text(
            key="chosen-label",
            content="Selected country:",
            style=Style(font_size=13.0),
        ),
        Row(
            key="chosen-row",
            style=Style(gap=8.0),
            children=[
                Text(
                    key="chosen-value",
                    content=s.committed,
                    style=Style(font_size=18.0),
                ),
                Button(
                    key="clear-btn",
                    label="Clear",
                    on_click=on_clear,
                    style=Style(
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=6.0,
                    ),
                ),
            ],
        ),
    ]
else:
    result_children = [
        Text(
            key="prompt",
            content="Type a country name or pick one from the suggestions.",
            style=Style(font_size=14.0),
        ),
    ]
```

The `view` builds the result panel's children list **before** assembling the
final tree. When `committed` is set, it shows the name prominently plus a
"Clear" button. When it is not, it shows a brief instruction.

Building `result_children` before the `return Column(...)` keeps the code
readable: the main tree stays clean, without `if/else` branches nested in the
middle of widget arguments.

!!! tip "Tip"
    This pattern — pre-computing children lists — is recommended whenever the
    tree has conditional branches. It avoids deeply nested ternary expressions
    inside parent widget arguments.

---

### 7. `Wrap` layout

```python
Wrap(
    key="categories",
    style=Style(gap=8.0),
    children=category_chips,
),
```

`Wrap` is a container that positions children in a row and **wraps to the next
line** automatically when horizontal space runs out. For three short chips this
rarely matters, but with many categories (or on narrow screens) the behaviour
becomes essential — unlike `Row`, which would overflow the container.

---

### 8. `Edge.symmetric` for asymmetric padding

```python
style=Style(
    padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
    radius=6.0,
),
```

`Edge.symmetric` creates an `Edge` with `top=bottom=vertical` and
`left=right=horizontal` — a convenient shorthand for button padding ("wider than
tall"). Compare with `Edge.all(n)` (same value on all four sides) and
`Edge(top, right, bottom, left)` (full control).

---

## Running the app 🚀

Save the file at `examples/search-autocomplete/app.py` and choose a mode:

=== "WASM mode (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/search-autocomplete
    ```

    Pyodide loads full Python in the browser. No server, no WebSocket — the
    Python handlers run locally in the tab.

=== "Server mode (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/search-autocomplete
    ```

    A FastAPI server starts locally. The JS client connects via WebSocket,
    sends typing/selection events, and receives diff patches back.

!!! check "Same code, two modes"
    Notice that `app.py` mentions neither `wasm` nor `server` anywhere. The
    transport boundary lives entirely inside `tempestweb` — you only choose at
    run time.

Open the browser at `http://localhost:8000` and try:

1. Click **"Americas"** — suggestions change to countries in the Americas.
2. Type `"bra"` — the list filters to `Brazil` immediately.
3. Click `Brazil` in the list — the result panel shows the selected country.
4. Click **"Clear"** — the field and result panel return to their initial state.

---

## Recap

In this example you learned:

- ✅ **`Autocomplete`** — text field with dynamic suggestions via `options`; two
  typed handlers: `on_change` (`TextChangeEvent`) and `on_select` (`SelectEvent`).
- ✅ **`Chip` with `selected`** — clickable pill with visual active/inactive state.
- ✅ **`Wrap`** — container that wraps children automatically, ideal for chip sets.
- ✅ **Derived state + `recompute()`** — centralises `suggestions` recalculation in a single method.
- ✅ **Factory closures in loops** — `_make_chip(cat)` captures each `cat` correctly; a direct lambda in the loop would be a trap.
- ✅ **Pre-computing conditional children** — builds `result_children` before `return` to keep the main tree readable.
- ✅ **`Edge.symmetric`** — shorthand for asymmetric padding (buttons, chips).

---

## Next steps

- Read the [Counter Tutorial](../tutorial/index.md) if you have not yet — it
  explains `set_state` and the rebuild cycle in depth.
- Compare with the [Login Form](login-form.md) example to see how `on_change`
  is used across multiple text fields.
- See how the [Profile Tabs](tabs-profile.en.md) example uses `Chip` in a
  navigation context.
- Explore other examples in the **Examples** section for more state and widget
  composition patterns.
