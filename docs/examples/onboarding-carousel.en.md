# Onboarding Carousel — Paged Navigation 🚀

Build a three-slide welcome flow with `PageView`, a dot indicator, Skip/Next/Get started buttons, and a completion screen — all in plain, typed Python.

---

## What you'll build

A classic onboarding carousel with:

- 📄 **Three introduction slides**, each with an icon, title, and description
- 🔵 **Dot indicator** centred below the pager, reflecting the active page
- ⏩ **Skip** button that jumps straight to the last slide
- ➡ **Next →** button that advances one page at a time
- ✅ **Get started** button (appears only on the last slide) that completes the flow
- 🎉 **Completion screen** displayed as soon as the user finishes onboarding

!!! note "Note — two navigation inputs"
    The page can change in two ways: a **swipe** from the user (emitted by the `PageView` via `PageChangeEvent`) or a **button click**. Both update the same `page` field in state — the widget tree always reflects a single source of truth.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading before you start:

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

Create the folder and the app file:

```bash
mkdir -p examples/onboarding-carousel
touch examples/onboarding-carousel/app.py
```

---

## Step 1 — Defining slide data

Before any UI, define the slide content in a list of dictionaries. This keeps copy separate from presentation logic:

```python
from __future__ import annotations

_SLIDES: list[dict[str, str]] = [
    {
        "icon": "🚀",
        "title": "Welcome to TempestWeb",
        "body": (
            "Build rich web apps in plain, typed Python. "
            "Write once — deploy as WASM in the browser or "
            "as a server-side stream over WebSocket."
        ),
    },
    {
        "icon": "🌊",
        "title": "One tree, two modes",
        "body": (
            "Your view function returns a widget tree that never names a "
            "transport.  The framework picks the mode; your code stays clean, "
            "diffable and fully type-checked."
        ),
    },
    {
        "icon": "⚡",
        "title": "Ready to ship",
        "body": (
            "Hot-reload in dev, static WASM bundle or FastAPI server in "
            "production.  Add push notifications, offline support and native "
            "device features with zero extra boilerplate."
        ),
    },
]

_TOTAL: int = len(_SLIDES)
```

!!! tip "Tip — extract data from the UI"
    Keeping copy in `_SLIDES` (outside of `view`) makes translation, testing, and future API-driven content straightforward. The `view` function does not need to know _what_ is written — only _how many_ slides exist and _which one_ is active.

---

## Step 2 — Defining state

The carousel state only needs to track two things:

| Field | Type | Meaning |
|---|---|---|
| `page` | `int` | Active page index (zero-based) |
| `done` | `bool` | Has the user completed onboarding? |

```python
from dataclasses import dataclass


@dataclass
class OnboardingState:
    """Mutable state for the onboarding carousel.

    Attributes:
        page: Active page index (0-based, 0 ≤ page < _TOTAL).
        done: Whether the user has completed the onboarding flow.
    """

    page: int = 0
    done: bool = False


def make_state() -> OnboardingState:
    """Build the initial onboarding state.

    Returns:
        A fresh :class:`OnboardingState` positioned on the first slide.
    """
    return OnboardingState()
```

!!! info "Note — `done` is not derived from `page`"
    You might wonder: "why keep `done` if I can just check `page == _TOTAL - 1`?" The answer is that being on the last slide does not mean the user has finished — they may simply be reading. Clicking **Get started** is the explicit signal of completion, and that moment must be captured in its own state field.

---

## Step 3 — Sub-builders: dot indicator and slide

Before assembling `view`, write two pure helper functions that build parts of the UI. This keeps `view` readable.

### 3.1 — The dot indicator

Receives the active index and the total number of pages; returns a `Row` of circular `Container` widgets. The active dot is larger and coloured with `ACCENT`; the others are muted grey.

```python
from tempest_core import Button, Column, Row, Style, Widget
from tempest_core.components import ACCENT, BACKGROUND, ON_MUTED, ON_SURFACE, Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Container, PageView, Text
from tempest_core.widgets.events import PageChangeEvent


def _dot_indicator(active: int, total: int) -> Widget:
    """Render a row of pagination dots.

    The active page's dot is highlighted in ``ACCENT`` and slightly larger;
    inactive dots are muted.

    Args:
        active: The currently active page index (0-based).
        total: The total number of pages.

    Returns:
        A ``Row`` of ``Container`` dots.
    """
    dots: list[Widget] = []
    for i in range(total):
        is_active: bool = i == active
        size: float = 10.0 if is_active else 8.0
        bg: Color = ACCENT if is_active else Color.from_hex("#4b5563")
        dots.append(
            Container(
                key=f"dot-{i}",
                style=Style(
                    width=size,
                    height=size,
                    radius=size / 2.0,
                    background=bg,
                    margin=Edge.symmetric(horizontal=4.0),
                ),
            )
        )
    return Row(
        key="dot-row",
        style=Style(justify=JustifyContent.CENTER, align=AlignItems.CENTER),
        children=dots,
    )
```

!!! tip "Tip — `radius=size / 2.0` for perfect circles"
    Setting `radius` to half the width/height turns a rectangular `Container` into a perfect circle. This is simpler than trying to apply `border-radius: 50%` as a raw string — the typed style system handles the CSS conversion automatically.

### 3.2 — A single slide

Each slide is a centred `Column` with an icon, title, and body text:

```python
def _slide(index: int) -> Widget:
    """Render one onboarding slide.

    Each slide contains a large emoji icon, a bold headline and a
    multi-line description, all centred on a dark surface card.

    Args:
        index: The slide index into :data:`_SLIDES`.

    Returns:
        A ``Column`` composing the slide content.
    """
    data: dict[str, str] = _SLIDES[index]
    return Column(
        key=f"slide-{index}",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(32.0),
            gap=24.0,
            background=BACKGROUND,
            min_height=380.0,
        ),
        children=[
            Text(
                content=data["icon"],
                key=f"slide-icon-{index}",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content=data["title"],
                key=f"slide-title-{index}",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content=data["body"],
                key=f"slide-body-{index}",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    line_height=1.6,
                    max_width=480.0,
                ),
            ),
        ],
    )
```

### 3.3 — The completion screen

When the user clicks **Get started**, `state.done` becomes `True` and the carousel is replaced by this thank-you card:

```python
def _done_card() -> Widget:
    """Render the post-onboarding thank-you card.

    Displayed once the user taps ``Get started`` on the final slide,
    confirming that the onboarding flow has been completed.

    Returns:
        A centred ``Column`` with a success icon and confirmation text.
    """
    return Column(
        key="done-card",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(40.0),
            gap=20.0,
            min_height=380.0,
        ),
        children=[
            Text(
                content="✅",
                key="done-icon",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content="You're all set!",
                key="done-title",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content="Onboarding complete. Enjoy building with TempestWeb.",
                key="done-body",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    max_width=400.0,
                ),
            ),
            Card(
                key="start-card",
                children=[
                    Text(
                        content="Head over to the examples to see what's possible.",
                        key="start-hint",
                        style=Style(
                            font_size=14.0,
                            color=ON_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ],
    )
```

---

## Step 4 — Event handlers

Inside `view()`, define five functions that react to user interactions. Each one calls `app.set_state(mutator)`:

```python
from tempest_core import App


def view(app: App[OnboardingState]) -> Widget:
    """Render the onboarding carousel from the current state."""
    state: OnboardingState = app.state
    is_last: bool = state.page == _TOTAL - 1

    def on_page_change(event: PageChangeEvent) -> None:
        """Synchronise state when the user swipes the PageView.

        Guards against feedback loops: if the emitted page already matches the
        state, the write is skipped.

        Args:
            event: The page-change event carrying the new page index.
        """
        if event.page == state.page:
            return
        app.set_state(lambda s: setattr(s, "page", event.page))

    def go_to_page(target: int) -> None:
        """Navigate to a specific slide index.

        Args:
            target: The destination page (clamped to 0 ≤ target < _TOTAL).
        """
        clamped: int = max(0, min(target, _TOTAL - 1))
        app.set_state(lambda s: setattr(s, "page", clamped))

    def on_skip() -> None:
        """Jump directly to the last slide when Skip is tapped."""
        go_to_page(_TOTAL - 1)

    def on_next() -> None:
        """Advance to the next slide, or mark onboarding done on the last slide."""
        if is_last:
            app.set_state(lambda s: setattr(s, "done", True))
        else:
            go_to_page(state.page + 1)
```

!!! warning "Warning — guard against feedback loops in `on_page_change`"
    The `PageView` can emit a `PageChangeEvent` even when the page already matches the state (for example, after an animation snap settles). Without the guard `if event.page == state.page: return`, each such emission would trigger an unnecessary `set_state`, re-rendering the tree for nothing. Always protect position-event handlers this way.

---

## Step 5 — Assembling the complete `view`

With the helpers and handlers ready, the main `view` only needs to orchestrate:

1. Check `state.done` and return the completion screen if true.
2. Build the slide list.
3. Assemble the control bar (Skip / dots / Next).
4. Compose everything into a root `Column`.

```python
    # --- Completion screen --------------------------------------------------

    if state.done:
        return Column(
            key="onboarding-root",
            style=Style(
                background=BACKGROUND,
                padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
                gap=0.0,
            ),
            children=[_done_card()],
        )

    # --- Carousel + controls ------------------------------------------------

    slides: list[Widget] = [_slide(i) for i in range(_TOTAL)]

    controls: list[Widget] = [
        # Skip button — only shown when not on the last slide
        Button(
            label="Skip",
            on_click=on_skip,
            key="btn-skip",
            style=Style(color=ON_MUTED),
        )
        if not is_last
        else Container(key="skip-spacer", style=Style(width=60.0)),
        # Dot indicator in the centre
        _dot_indicator(active=state.page, total=_TOTAL),
        # Next / Get started
        Button(
            label="Get started" if is_last else "Next →",
            on_click=on_next,
            key="btn-next",
            style=Style(
                background=ACCENT,
                color=ON_SURFACE,
                padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
                radius=8.0,
                font_weight=FontWeight.SEMIBOLD,
            ),
        ),
    ]

    return Column(
        key="onboarding-root",
        style=Style(
            background=BACKGROUND,
            padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
            gap=24.0,
        ),
        children=[
            # Header label
            Text(
                content=f"Step {state.page + 1} of {_TOTAL}",
                key="step-label",
                style=Style(
                    font_size=12.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Paged carousel
            PageView(
                key="onboarding-pager",
                page=state.page,
                on_page_change=on_page_change,
                children=slides,
            ),
            # Skip / dots / Next row
            Row(
                key="controls-row",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(horizontal=8.0),
                ),
                children=controls,
            ),
        ],
    )
```

!!! tip "Tip — `Container` as a spacer"
    On the last slide, the **Skip** button needs to disappear, but the `Row` with `JustifyContent.SPACE_BETWEEN` still requires three children to keep the layout balanced. Using `Container(key="skip-spacer", style=Style(width=60.0))` in its place ensures the dots and **Get started** button stay centred without changing the tree structure.

---

## The complete app

Here is the complete file, ready to copy:

```python
"""Onboarding carousel — paged navigation demo.

A multi-step onboarding flow built with :class:`~tempest_core.widgets.PageView`.
Three full-width slides walk the user through a product introduction; a dot
indicator below the pager tracks the active page, and ``Skip`` / ``Next``
buttons (replaced by a ``Get started`` button on the last slide) let the user
navigate without swiping.

Demonstrates:

* :class:`~tempest_core.widgets.PageView` driven by ``page`` state.
* :class:`~tempest_core.widgets.events.PageChangeEvent` — fired when the
  user swipes; the handler ignores events that would land on the current page to
  break feedback loops.
* Dot-indicator pattern: three ``Container`` widgets styled conditionally on the
  active-page index.
* ``Skip`` button that jumps straight to the last slide.
* ``Next`` / ``Get started`` buttons that advance the page or conclude the flow,
  with the conclusion reflected in a thank-you card.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Widget
from tempest_core.components import ACCENT, BACKGROUND, ON_MUTED, ON_SURFACE, Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Container, PageView, Text
from tempest_core.widgets.events import PageChangeEvent

# ---------------------------------------------------------------------------
# Slide data
# ---------------------------------------------------------------------------

_SLIDES: list[dict[str, str]] = [
    {
        "icon": "🚀",
        "title": "Welcome to TempestWeb",
        "body": (
            "Build rich web apps in plain, typed Python. "
            "Write once — deploy as WASM in the browser or "
            "as a server-side stream over WebSocket."
        ),
    },
    {
        "icon": "🌊",
        "title": "One tree, two modes",
        "body": (
            "Your view function returns a widget tree that never names a "
            "transport.  The framework picks the mode; your code stays clean, "
            "diffable and fully type-checked."
        ),
    },
    {
        "icon": "⚡",
        "title": "Ready to ship",
        "body": (
            "Hot-reload in dev, static WASM bundle or FastAPI server in "
            "production.  Add push notifications, offline support and native "
            "device features with zero extra boilerplate."
        ),
    },
]

_TOTAL: int = len(_SLIDES)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class OnboardingState:
    """Mutable state for the onboarding carousel.

    Attributes:
        page: Active page index (0-based, 0 ≤ page < _TOTAL).
        done: Whether the user has completed the onboarding flow.
    """

    page: int = 0
    done: bool = False


def make_state() -> OnboardingState:
    """Build the initial onboarding state.

    Returns:
        A fresh :class:`OnboardingState` positioned on the first slide.
    """
    return OnboardingState()


# ---------------------------------------------------------------------------
# Sub-builders
# ---------------------------------------------------------------------------


def _dot_indicator(active: int, total: int) -> Widget:
    """Render a row of pagination dots.

    The active page's dot is highlighted in ``ACCENT`` and slightly larger;
    inactive dots are muted.

    Args:
        active: The currently active page index (0-based).
        total: The total number of pages.

    Returns:
        A ``Row`` of ``Container`` dots.
    """
    dots: list[Widget] = []
    for i in range(total):
        is_active: bool = i == active
        size: float = 10.0 if is_active else 8.0
        bg: Color = ACCENT if is_active else Color.from_hex("#4b5563")
        dots.append(
            Container(
                key=f"dot-{i}",
                style=Style(
                    width=size,
                    height=size,
                    radius=size / 2.0,
                    background=bg,
                    margin=Edge.symmetric(horizontal=4.0),
                ),
            )
        )
    return Row(
        key="dot-row",
        style=Style(justify=JustifyContent.CENTER, align=AlignItems.CENTER),
        children=dots,
    )


def _slide(index: int) -> Widget:
    """Render one onboarding slide.

    Each slide contains a large emoji icon, a bold headline and a
    multi-line description, all centred on a dark surface card.

    Args:
        index: The slide index into :data:`_SLIDES`.

    Returns:
        A ``Column`` composing the slide content.
    """
    data: dict[str, str] = _SLIDES[index]
    return Column(
        key=f"slide-{index}",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(32.0),
            gap=24.0,
            background=BACKGROUND,
            min_height=380.0,
        ),
        children=[
            Text(
                content=data["icon"],
                key=f"slide-icon-{index}",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content=data["title"],
                key=f"slide-title-{index}",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content=data["body"],
                key=f"slide-body-{index}",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    line_height=1.6,
                    max_width=480.0,
                ),
            ),
        ],
    )


def _done_card() -> Widget:
    """Render the post-onboarding thank-you card.

    Displayed once the user taps ``Get started`` on the final slide,
    confirming that the onboarding flow has been completed.

    Returns:
        A centred ``Column`` with a success icon and confirmation text.
    """
    return Column(
        key="done-card",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(40.0),
            gap=20.0,
            min_height=380.0,
        ),
        children=[
            Text(
                content="✅",
                key="done-icon",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content="You're all set!",
                key="done-title",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content="Onboarding complete. Enjoy building with TempestWeb.",
                key="done-body",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    max_width=400.0,
                ),
            ),
            Card(
                key="start-card",
                children=[
                    Text(
                        content="Head over to the examples to see what's possible.",
                        key="start-hint",
                        style=Style(
                            font_size=14.0,
                            color=ON_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[OnboardingState]) -> Widget:
    """Render the onboarding carousel from the current state.

    The active page index lives in ``app.state.page`` and is updated both by
    the ``PageView``'s ``on_page_change`` handler (swipe gesture) and by the
    ``Skip`` / ``Next`` / ``Get started`` buttons.

    When ``app.state.done`` is ``True``, the ``PageView`` is replaced by a
    completion card so the user sees clear feedback that onboarding finished.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: OnboardingState = app.state
    is_last: bool = state.page == _TOTAL - 1

    # --- Handlers -----------------------------------------------------------

    def on_page_change(event: PageChangeEvent) -> None:
        """Synchronise state when the user swipes the PageView.

        Guards against feedback loops: if the emitted page already matches the
        state, the write is skipped.

        Args:
            event: The page-change event carrying the new page index.
        """
        if event.page == state.page:
            return
        app.set_state(lambda s: setattr(s, "page", event.page))

    def go_to_page(target: int) -> None:
        """Navigate to a specific slide index.

        Args:
            target: The destination page (clamped to 0 ≤ target < _TOTAL).
        """
        clamped: int = max(0, min(target, _TOTAL - 1))
        app.set_state(lambda s: setattr(s, "page", clamped))

    def on_skip() -> None:
        """Jump directly to the last slide when Skip is tapped."""
        go_to_page(_TOTAL - 1)

    def on_next() -> None:
        """Advance to the next slide, or mark onboarding done on the last slide."""
        if is_last:
            app.set_state(lambda s: setattr(s, "done", True))
        else:
            go_to_page(state.page + 1)

    # --- Completion screen --------------------------------------------------

    if state.done:
        return Column(
            key="onboarding-root",
            style=Style(
                background=BACKGROUND,
                padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
                gap=0.0,
            ),
            children=[_done_card()],
        )

    # --- Carousel + controls ------------------------------------------------

    slides: list[Widget] = [_slide(i) for i in range(_TOTAL)]

    controls: list[Widget] = [
        # Skip button — only shown when not on the last slide
        Button(
            label="Skip",
            on_click=on_skip,
            key="btn-skip",
            style=Style(color=ON_MUTED),
        )
        if not is_last
        else Container(key="skip-spacer", style=Style(width=60.0)),
        # Dot indicator in the centre
        _dot_indicator(active=state.page, total=_TOTAL),
        # Next / Get started
        Button(
            label="Get started" if is_last else "Next →",
            on_click=on_next,
            key="btn-next",
            style=Style(
                background=ACCENT,
                color=ON_SURFACE,
                padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
                radius=8.0,
                font_weight=FontWeight.SEMIBOLD,
            ),
        ),
    ]

    return Column(
        key="onboarding-root",
        style=Style(
            background=BACKGROUND,
            padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
            gap=24.0,
        ),
        children=[
            # Header label
            Text(
                content=f"Step {state.page + 1} of {_TOTAL}",
                key="step-label",
                style=Style(
                    font_size=12.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Paged carousel
            PageView(
                key="onboarding-pager",
                page=state.page,
                on_page_change=on_page_change,
                children=slides,
            ),
            # Skip / dots / Next row
            Row(
                key="controls-row",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(horizontal=8.0),
                ),
                children=controls,
            ),
        ],
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/onboarding-carousel/app.py
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/onboarding-carousel/app.py
```

Python runs on the server; the browser receives JSON patches over the WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode you should see:

    1. Label **"Step 1 of 3"** at the top
    2. Slide 1 with the 🚀 icon, title, and description
    3. Control bar: **Skip** on the left, three dots in the centre, **Next →** on the right
    4. Click **Next →** → slide advances, label changes to "Step 2 of 3", middle dot lights up
    5. Click **Skip** on any slide before the last → jumps to slide 3, button becomes **Get started**
    6. On slide 3, the **Skip** button disappears (replaced by a transparent spacer)
    7. Click **Get started** → carousel is replaced by the ✅ "You're all set!" screen

---

## Automated verification ✅

Run all four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All four must pass green. The example is specifically designed to be `mypy --strict` clean — every variable, parameter, and return value is explicitly annotated.

---

## How it works under the hood

### The update cycle

```
Swipe or button click
         │
         ▼
handler (on_page_change / on_skip / on_next)
         │
         ▼
app.set_state(lambda s: setattr(s, "page", new_value))
         │
         ▼
tempestweb applies the mutator → new state
         │
         ▼
view(app) called again → new widget tree
         │
         ▼
reconciler calculates diff (minimal patches)
         │
         ▼
DOM updated — only the changed nodes
```

### `PageView` and two navigation sources

The `PageView` exposes `page=` (the source of truth flowing from Python state) and `on_page_change=` (a callback for when the user swipes). This separation ensures Python _always_ owns which page is active:

- Button clicked → handler calls `go_to_page` → `set_state` → re-render → `PageView` receives new `page=`
- User swipes → `PageView` emits `PageChangeEvent` → `on_page_change` calls `set_state` → re-render confirms the position

Both paths converge on the same `state.page`. There is never "local" state inside the `PageView` that could diverge from Python.

### Why `key` matters here

The reconciler uses `key` to identify nodes between renders. Slides have `key=f"slide-{index}"` and dots have `key=f"dot-{i}"`. This means that when the page changes, only the nodes that actually changed (the dot background, the visible slide) receive patches — not a full tree rebuild.

---

## Recap

In this tutorial you learned:

- ✅ Use **`PageView`** with the `page=` prop for state-controlled navigation
- ✅ Handle **`PageChangeEvent`** with an anti-feedback-loop guard
- ✅ Build a **dot indicator** dynamically with circular `Container` widgets
- ✅ Switch the button label between **"Next →"** and **"Get started"** based on `is_last`
- ✅ Use a **`Container` spacer** to keep the layout stable when a button disappears
- ✅ Model **completion state** (`done: bool`) separately from position (`page: int`)
- ✅ Extract sub-builders (`_slide`, `_dot_indicator`, `_done_card`) to keep `view` readable

---

## Next steps

Try extending the example:

- 💡 Add slide transition animations using the `_core` animation module
- 💡 Persist `done` to `localStorage` via Mode A's storage API so the onboarding is not shown again
- 💡 Add a fourth slide with a registration form — see the [BR Cadastro](./br-cadastro.en.md) example
- 💡 Explore [Signup Wizard](./signup-wizard.en.md) for a paged flow with per-step validation
- 💡 Read the [Basic tutorial](../tutorial/index.md) to understand the `view` → `set_state` cycle in depth
