# Rating & Review Form

> 🚀 **What you'll build:** a complete product-review form — clickable star rating with `Rating`, togglable aspect tags with `Chip`, a free-text area with `TextArea`, inline validation, and a read-only summary card shown after submission.

---

## Why this example matters

Review forms appear everywhere — shops, services, delivery apps.
They combine three types of selection control in a single flow:

| Control | Widget | Purpose |
|---|---|---|
| Star rating | `Rating` | Integer value from 1 to N |
| Aspect tags | `Chip` | Multi-select via toggle |
| Free text | `TextArea` | Narrative body with character counter |

In this tutorial you will learn how to:

- Use `Rating` to capture an integer star rating;
- Create toggle handlers with a closure factory for `Chip`;
- Synchronize `TextArea` via `TextChangeEvent`;
- Display an inline validation error before accepting the submission;
- Show a summary card after submission and reset the form.

!!! note "Note"
    This example runs **without any changes** in both modes — WASM (Pyodide in
    the browser) and Server (FastAPI + WebSocket). The same Python `view()` serves
    both.

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
└── rating-review/
    └── app.py
```

Create the folder and the file:

```bash
mkdir -p examples/rating-review
touch examples/rating-review/app.py
```

---

## Step 1 — Imports and tag catalogue

Start by declaring the imports and the list of aspect keywords the reviewer can
toggle as tags.

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import Card, Chip, Divider, Rating
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Button, Column, Row, Text, TextArea, Wrap
from tempest_core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Chip tag catalogue — aspect keywords the reviewer can toggle.
# ---------------------------------------------------------------------------
_ALL_TAGS: list[str] = [
    "Quality",
    "Value for money",
    "Fast delivery",
    "Great packaging",
    "Accurate description",
    "Good customer service",
    "Would recommend",
]
```

!!! tip "Tip"
    `_ALL_TAGS` is a module-level constant — it does not live in the state because
    it never changes. The state only tracks which tags are currently *selected*.

**What just happened:**

- The `Rating` and `Chip` components come from `tempest_core.components`.
- `Wrap` (from `tempest_core.widgets`) distributes children across multiple
  lines automatically when space runs out — ideal for variable-width chip sets.
- `TextChangeEvent` is the event fired by `TextArea` on every keystroke.

---

## Step 2 — Define the state

The state models all mutable form data plus the post-submission result.

```python
@dataclass
class Review:
    """A completed review assembled from the form.

    Attributes:
        rating: The 1-based star rating chosen by the reviewer.
        tags: The aspect keywords selected by the reviewer.
        body: The free-text review body.
    """

    rating: int
    tags: list[str]
    body: str


@dataclass
class ReviewState:
    """State for the rating & review app.

    Attributes:
        rating: The currently selected star rating (0 = none chosen yet).
        selected_tags: The set of tag labels currently toggled on.
        body: The current text in the review TextArea.
        error: An inline validation message shown near the submit button.
        submitted_review: The assembled review after a valid submission, or
            ``None`` while the form is still being filled in.
    """

    rating: int = 0
    selected_tags: list[str] = field(default_factory=list)
    body: str = ""
    error: str = ""
    submitted_review: Review | None = None


def make_state() -> ReviewState:
    """Build the initial, empty review state.

    Returns:
        A fresh :class:`ReviewState` with nothing selected.
    """
    return ReviewState()
```

!!! info "Info"
    `submitted_review: Review | None = None` acts as a **view mode selector**.
    While it is `None`, `view` renders the interactive form. Once populated, it
    renders the summary card — a view swap without a route change.

**Two dataclasses, separate responsibilities:**

- `Review` is **immutable after construction** — it represents the finished review.
- `ReviewState` is **mutable** — it represents the work-in-progress form data.

---

## Step 3 — Event handlers

Before building the layout, define the four functions that respond to user
interactions. They are created inside `view()` so they can capture `app` in their
closure.

```python
def view(app: App[ReviewState]) -> Widget:
    """Render the rating & review form (or summary) from the current state.

    When ``state.submitted_review`` is set the function renders a read-only
    summary card; otherwise it renders the interactive form so the user can
    fill in stars, tags and a text body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: ReviewState = app.state

    # ... (the summary view comes later — see Step 5)

    def set_rating(value: int) -> None:
        """Update the star rating in state.

        Args:
            value: The 1-based star value reported by the Rating component.
        """
        app.set_state(lambda s: setattr(s, "rating", value))

    def make_tag_handler(tag: str) -> Callable[[], None]:
        """Return a click handler that toggles ``tag`` in the selection list.

        Args:
            tag: The chip label to toggle on or off.

        Returns:
            A zero-argument handler that flips the tag's membership in
            ``state.selected_tags``.
        """

        def handler() -> None:
            def mutate(s: ReviewState) -> None:
                if tag in s.selected_tags:
                    s.selected_tags = [t for t in s.selected_tags if t != tag]
                else:
                    s.selected_tags = [*s.selected_tags, tag]

            app.set_state(mutate)

        return handler

    def edit_body(event: TextChangeEvent) -> None:
        """Synchronize the TextArea value into state.

        Args:
            event: The change event carrying the new text value.
        """
        app.set_state(lambda s: setattr(s, "body", event.value))

    def submit() -> None:
        """Validate the form and, when valid, assemble and store the review."""

        def mutate(s: ReviewState) -> None:
            if s.rating == 0:
                s.error = "Please select at least one star."
                return
            if not s.body.strip():
                s.error = "Please write a short review before submitting."
                return
            s.error = ""
            s.submitted_review = Review(
                rating=s.rating,
                tags=list(s.selected_tags),
                body=s.body.strip(),
            )

        app.set_state(mutate)
```

!!! tip "Tip — closure factory for `Chip`"
    `make_tag_handler(tag)` returns a different handler for each tag.
    If you used `lambda: toggle(tag)` directly inside a loop, **all lambdas would
    capture the same `tag`** (the last value of the iterator). The factory creates
    a new scope on each call, ensuring each chip toggles only its own label.

**Handler responsibilities:**

| Handler | Fires when | What it does |
|---|---|---|
| `set_rating(value)` | User clicks a star | Writes `value` into `state.rating` |
| `make_tag_handler(tag)` | User clicks a chip | Adds or removes `tag` from `selected_tags` |
| `edit_body(event)` | User types in `TextArea` | Writes `event.value` into `state.body` |
| `submit()` | User clicks "Submit review" | Validates and, if ok, assembles `Review` |

---

## Step 4 — Form layout

Now assemble the widget tree. The `Rating` sits inside a `Row` next to the text
hint; the `Chip`s live inside a `Wrap` that wraps automatically; the `TextArea`
shows a character counter below it.

```python
    # ------------------------------------------------------------------
    # Star rating label
    # ------------------------------------------------------------------
    rating_labels: dict[int, str] = {
        0: "Tap a star to rate",
        1: "Poor",
        2: "Fair",
        3: "Good",
        4: "Very good",
        5: "Excellent",
    }
    rating_hint: str = rating_labels.get(state.rating, "")

    # ------------------------------------------------------------------
    # Chip row
    # ------------------------------------------------------------------
    chip_widgets: list[Widget] = [
        Chip(
            key=f"chip-{tag}",
            label=tag,
            selected=tag in state.selected_tags,
            on_click=make_tag_handler(tag),
        )
        for tag in _ALL_TAGS
    ]

    # ------------------------------------------------------------------
    # Form layout
    # ------------------------------------------------------------------
    form_children: list[Widget] = [
        # --- Heading ---
        Text(
            content="Leave a review",
            key="heading",
            style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="heading-div"),
        # --- Star rating section ---
        Text(
            content="Overall rating",
            key="rating-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Row(
            key="rating-row",
            style=Style(gap=12.0),
            children=[
                Rating(
                    key="stars",
                    value=state.rating,
                    max_stars=5,
                    on_rate=set_rating,
                ),
                Text(
                    content=rating_hint,
                    key="rating-hint",
                    style=Style(font_size=14.0),
                ),
            ],
        ),
        # --- Aspect tags section ---
        Text(
            content="What did you think of? (optional)",
            key="tags-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Wrap(
            key="chips",
            style=Style(gap=8.0),
            children=chip_widgets,
        ),
        # --- Review body ---
        Text(
            content="Your review",
            key="body-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        TextArea(
            key="body-input",
            value=state.body,
            placeholder="Share your experience with this product…",
            rows=5,
            max_length=1000,
            on_change=edit_body,
        ),
        Text(
            content=f"{len(state.body)}/1000 characters",
            key="char-count",
            style=Style(font_size=12.0),
        ),
    ]

    # Inline validation error (shown only when non-empty)
    if state.error:
        form_children.append(
            Text(
                content=state.error,
                key="error-msg",
                style=Style(font_size=14.0),
            )
        )

    form_children.append(
        Button(
            label="Submit review",
            on_click=submit,
            key="submit-btn",
        )
    )

    return Column(
        key="review-root",
        style=Style(gap=14.0, padding=Edge.all(20.0)),
        children=form_children,
    )
```

!!! info "Info — `Chip(selected=...)`"
    The `selected` parameter is recomputed on every render: `tag in state.selected_tags`.
    There is no internal state in `Chip` — the appearance (filled vs. outlined) is
    determined entirely by Python state. This is the essence of tempestweb's
    declarative model.

!!! tip "Tip — inline error vs. modal"
    Appending the error `Text` conditionally to the `form_children` list (rather
    than using two separate `return` branches) keeps the rest of the form visible.
    The user can fix the problem without losing what they already typed.

**Layout highlights:**

- `Rating(value=state.rating, max_stars=5, on_rate=set_rating)` — the component
  renders the stars; `on_rate` receives the clicked integer value.
- `Wrap` distributes children across multiple lines as space allows — ideal for
  chip sets of variable width.
- `TextArea(rows=5, max_length=1000)` — initial height in lines and character
  limit declared directly on the widget.
- The counter `f"{len(state.body)}/1000 characters"` is recomputed on every
  `TextChangeEvent` with no extra state needed.

---

## Step 5 — Post-submission summary card

When `state.submitted_review` is not `None`, `view` returns a completely different
layout — a read-only card with a reset button.

Add this block **at the top of `view`**, right after `state: ReviewState = app.state`:

```python
    # ------------------------------------------------------------------
    # Post-submission summary view
    # ------------------------------------------------------------------
    if state.submitted_review is not None:
        rev: Review = state.submitted_review
        stars_text: str = "★" * rev.rating + "☆" * (5 - rev.rating)
        tags_text: str = ", ".join(rev.tags) if rev.tags else "—"

        def _reset_mutate(s: ReviewState) -> None:
            s.submitted_review = None
            s.rating = 0
            s.selected_tags = []
            s.body = ""
            s.error = ""

        def reset_form() -> None:
            """Reset the form to initial state."""
            app.set_state(_reset_mutate)

        return Column(
            key="summary-root",
            style=Style(gap=16.0, padding=Edge.all(20.0)),
            children=[
                Text(
                    content="Review submitted!",
                    key="summary-heading",
                    style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
                ),
                Card(
                    key="summary-card",
                    children=[
                        Text(
                            content=f"Rating: {stars_text}",
                            key="sum-rating",
                            style=Style(font_size=18.0),
                        ),
                        Text(
                            content=f"Tags: {tags_text}",
                            key="sum-tags",
                            style=Style(font_size=14.0),
                        ),
                        Divider(key="sum-divider"),
                        Text(
                            content=rev.body,
                            key="sum-body",
                            style=Style(font_size=15.0),
                        ),
                    ],
                ),
                Button(
                    label="Write another review",
                    on_click=reset_form,
                    key="reset-btn",
                ),
            ],
        )
```

!!! warning "Warning — early return in `view`"
    The `return` inside `if state.submitted_review is not None` exits the function
    before the form is built. This is **intentional** — the same early-return
    pattern is used to show loading or error screens. The reconciler receives a
    completely different tree and applies the necessary DOM patches.

**Full state flow:**

```
rating=0, body="", submitted_review=None
        ↓ user fills the form and clicks "Submit review"
rating=4, body="Great product!", submitted_review=Review(...)
        ↓ reconciler swaps the tree
summary card appears
        ↓ user clicks "Write another review"
rating=0, body="", submitted_review=None
        ↓ form reappears
```

---

## Step 6 — Complete code

Here is the complete `app.py`, ready to copy and paste:

```python
"""Rating & review — exercises Rating stars, Chip tag toggles and TextArea.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The demo builds a complete product-review form:

* A :class:`~tempest_core.components.Rating` row lets the user pick 1–5 stars.
* A :class:`~tempest_core.widgets.Wrap` of togglable
  :class:`~tempest_core.components.Chip` widgets lets the user tag the review
  with relevant aspect keywords (e.g. "Quality", "Value for money").
* A :class:`~tempest_core.widgets.TextArea` collects the free-text body.
* A submit :class:`~tempest_core.widgets.Button` assembles and stores the
  finished review in the state, while a guard ensures at least one star and a
  non-empty body before accepting.

The assembled review is displayed as a read-only summary card after submission,
and a "Write another" button resets the form for the next review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import Card, Chip, Divider, Rating
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Button, Column, Row, Text, TextArea, Wrap
from tempest_core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Chip tag catalogue — aspect keywords the reviewer can toggle.
# ---------------------------------------------------------------------------
_ALL_TAGS: list[str] = [
    "Quality",
    "Value for money",
    "Fast delivery",
    "Great packaging",
    "Accurate description",
    "Good customer service",
    "Would recommend",
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class Review:
    """A completed review assembled from the form.

    Attributes:
        rating: The 1-based star rating chosen by the reviewer.
        tags: The aspect keywords selected by the reviewer.
        body: The free-text review body.
    """

    rating: int
    tags: list[str]
    body: str


@dataclass
class ReviewState:
    """State for the rating & review app.

    Attributes:
        rating: The currently selected star rating (0 = none chosen yet).
        selected_tags: The set of tag labels currently toggled on.
        body: The current text in the review TextArea.
        error: An inline validation message shown near the submit button.
        submitted_review: The assembled review after a valid submission, or
            ``None`` while the form is still being filled in.
    """

    rating: int = 0
    selected_tags: list[str] = field(default_factory=list)
    body: str = ""
    error: str = ""
    submitted_review: Review | None = None


def make_state() -> ReviewState:
    """Build the initial, empty review state.

    Returns:
        A fresh :class:`ReviewState` with nothing selected.
    """
    return ReviewState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[ReviewState]) -> Widget:
    """Render the rating & review form (or summary) from the current state.

    When ``state.submitted_review`` is set the function renders a read-only
    summary card; otherwise it renders the interactive form so the user can
    fill in stars, tags and a text body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: ReviewState = app.state

    # ------------------------------------------------------------------
    # Post-submission summary view
    # ------------------------------------------------------------------
    if state.submitted_review is not None:
        rev: Review = state.submitted_review
        stars_text: str = "★" * rev.rating + "☆" * (5 - rev.rating)
        tags_text: str = ", ".join(rev.tags) if rev.tags else "—"

        def _reset_mutate(s: ReviewState) -> None:
            s.submitted_review = None
            s.rating = 0
            s.selected_tags = []
            s.body = ""
            s.error = ""

        def reset_form() -> None:
            """Reset the form to initial state."""
            app.set_state(_reset_mutate)

        return Column(
            key="summary-root",
            style=Style(gap=16.0, padding=Edge.all(20.0)),
            children=[
                Text(
                    content="Review submitted!",
                    key="summary-heading",
                    style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
                ),
                Card(
                    key="summary-card",
                    children=[
                        Text(
                            content=f"Rating: {stars_text}",
                            key="sum-rating",
                            style=Style(font_size=18.0),
                        ),
                        Text(
                            content=f"Tags: {tags_text}",
                            key="sum-tags",
                            style=Style(font_size=14.0),
                        ),
                        Divider(key="sum-divider"),
                        Text(
                            content=rev.body,
                            key="sum-body",
                            style=Style(font_size=15.0),
                        ),
                    ],
                ),
                Button(
                    label="Write another review",
                    on_click=reset_form,
                    key="reset-btn",
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def set_rating(value: int) -> None:
        """Update the star rating in state.

        Args:
            value: The 1-based star value reported by the Rating component.
        """
        app.set_state(lambda s: setattr(s, "rating", value))

    def make_tag_handler(tag: str) -> Callable[[], None]:
        """Return a click handler that toggles ``tag`` in the selection list.

        Args:
            tag: The chip label to toggle on or off.

        Returns:
            A zero-argument handler that flips the tag's membership in
            ``state.selected_tags``.
        """

        def handler() -> None:
            def mutate(s: ReviewState) -> None:
                if tag in s.selected_tags:
                    s.selected_tags = [t for t in s.selected_tags if t != tag]
                else:
                    s.selected_tags = [*s.selected_tags, tag]

            app.set_state(mutate)

        return handler

    def edit_body(event: TextChangeEvent) -> None:
        """Synchronize the TextArea value into state.

        Args:
            event: The change event carrying the new text value.
        """
        app.set_state(lambda s: setattr(s, "body", event.value))

    def submit() -> None:
        """Validate the form and, when valid, assemble and store the review."""

        def mutate(s: ReviewState) -> None:
            if s.rating == 0:
                s.error = "Please select at least one star."
                return
            if not s.body.strip():
                s.error = "Please write a short review before submitting."
                return
            s.error = ""
            s.submitted_review = Review(
                rating=s.rating,
                tags=list(s.selected_tags),
                body=s.body.strip(),
            )

        app.set_state(mutate)

    # ------------------------------------------------------------------
    # Star rating label
    # ------------------------------------------------------------------
    rating_labels: dict[int, str] = {
        0: "Tap a star to rate",
        1: "Poor",
        2: "Fair",
        3: "Good",
        4: "Very good",
        5: "Excellent",
    }
    rating_hint: str = rating_labels.get(state.rating, "")

    # ------------------------------------------------------------------
    # Chip row
    # ------------------------------------------------------------------
    chip_widgets: list[Widget] = [
        Chip(
            key=f"chip-{tag}",
            label=tag,
            selected=tag in state.selected_tags,
            on_click=make_tag_handler(tag),
        )
        for tag in _ALL_TAGS
    ]

    # ------------------------------------------------------------------
    # Form layout
    # ------------------------------------------------------------------
    form_children: list[Widget] = [
        # --- Heading ---
        Text(
            content="Leave a review",
            key="heading",
            style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="heading-div"),
        # --- Star rating section ---
        Text(
            content="Overall rating",
            key="rating-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Row(
            key="rating-row",
            style=Style(gap=12.0),
            children=[
                Rating(
                    key="stars",
                    value=state.rating,
                    max_stars=5,
                    on_rate=set_rating,
                ),
                Text(
                    content=rating_hint,
                    key="rating-hint",
                    style=Style(font_size=14.0),
                ),
            ],
        ),
        # --- Aspect tags section ---
        Text(
            content="What did you think of? (optional)",
            key="tags-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Wrap(
            key="chips",
            style=Style(gap=8.0),
            children=chip_widgets,
        ),
        # --- Review body ---
        Text(
            content="Your review",
            key="body-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        TextArea(
            key="body-input",
            value=state.body,
            placeholder="Share your experience with this product…",
            rows=5,
            max_length=1000,
            on_change=edit_body,
        ),
        Text(
            content=f"{len(state.body)}/1000 characters",
            key="char-count",
            style=Style(font_size=12.0),
        ),
    ]

    # Inline validation error (shown only when non-empty)
    if state.error:
        form_children.append(
            Text(
                content=state.error,
                key="error-msg",
                style=Style(font_size=14.0),
            )
        )

    form_children.append(
        Button(
            label="Submit review",
            on_click=submit,
            key="submit-btn",
        )
    )

    return Column(
        key="review-root",
        style=Style(gap=14.0, padding=Edge.all(20.0)),
        children=form_children,
    )
```

---

## Step 7 — Run the app

Run in **Mode A** (Python in the browser via Pyodide):

```bash
tempestweb dev --mode wasm --path examples/rating-review
```

Run in **Mode B** (Python on the server via FastAPI + WebSocket):

```bash
tempestweb run --mode server --path examples/rating-review
```

Open `http://localhost:8000` in your browser. You should see:

- ✅ "Leave a review" heading in bold with a `Divider` below;
- ✅ Five clickable stars — the text hint updates as the rating changes;
- ✅ Seven togglable aspect chips that appear filled when selected;
- ✅ `TextArea` with a `0/1000` character counter updated in real time;
- ✅ Clicking "Submit review" with no rating shows the inline error;
- ✅ A valid submission swaps the form for the summary card;
- ✅ "Write another review" resets everything back to the initial state.

---

## Recap

In this tutorial you built a complete review form and learned:

- 💡 **`Rating(value=..., max_stars=5, on_rate=handler)`** — receives an integer
  and calls `handler(value)` on click. No internal state: the appearance is driven
  by `value` from Python state.
- 💡 **`Chip(selected=..., on_click=handler)`** — the filled/outlined visual comes
  from `selected`; use a closure factory (`make_tag_handler`) to generate a distinct
  handler per chip inside loops.
- 💡 **`TextArea(value=..., on_change=handler)`** — sync via `event.value` in the
  `TextChangeEvent`; the character counter is derived directly from state.
- 💡 **`Wrap`** distributes children across multiple lines — ideal for variable-width
  chip sets.
- 💡 **Inline validation** — append or omit the error widget conditionally in the
  `form_children` list rather than using two separate `return` branches. The user
  keeps whatever they already filled in.
- 💡 **`submitted_review: Review | None`** acts as a mode selector: `None` → form;
  populated → summary card. No extra route needed.
- 💡 The same `app.py` runs in both modes — WASM and Server — without any changes.

---

## Next steps

- Read the [core tutorial](../tutorial/index.md) to understand the full tempestweb
  lifecycle.
- Explore the [login-form](login-form.en.md) example for per-field validation
  feedback.
- See [signup-wizard](signup-wizard.en.md) for a multi-step form with a progress
  bar.
- Check [data-table](data-table.en.md) to display the collected reviews in a
  tabular format.
