"""Rating & review — exercises Rating stars, Chip tag toggles and TextArea.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The demo builds a complete product-review form:

* A :class:`~tempestweb._core.components.Rating` row lets the user pick 1–5 stars.
* A :class:`~tempestweb._core.widgets.Wrap` of togglable
  :class:`~tempestweb._core.components.Chip` widgets lets the user tag the review
  with relevant aspect keywords (e.g. "Quality", "Value for money").
* A :class:`~tempestweb._core.widgets.TextArea` collects the free-text body.
* A submit :class:`~tempestweb._core.widgets.Button` assembles and stores the
  finished review in the state, while a guard ensures at least one star and a
  non-empty body before accepting.

The assembled review is displayed as a read-only summary card after submission,
and a "Write another" button resets the form for the next review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card, Chip, Divider, Rating
from tempestweb._core.style import Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Row, Text, TextArea, Wrap
from tempestweb._core.widgets.events import TextChangeEvent

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
