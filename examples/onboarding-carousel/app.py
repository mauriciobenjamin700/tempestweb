"""Onboarding carousel — paged navigation demo.

A multi-step onboarding flow built with :class:`~tempestweb._core.widgets.PageView`.
Three full-width slides walk the user through a product introduction; a dot
indicator below the pager tracks the active page, and ``Skip`` / ``Next``
buttons (replaced by a ``Get started`` button on the last slide) let the user
navigate without swiping.

Demonstrates:

* :class:`~tempestweb._core.widgets.PageView` driven by ``page`` state.
* :class:`~tempestweb._core.widgets.events.PageChangeEvent` — fired when the
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

from tempestweb._core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempestweb._core.widgets.events import PageChangeEvent

from tempestweb._core import App, Button, Column, Row, Style, Widget
from tempestweb._core.components import ACCENT, BACKGROUND, ON_MUTED, ON_SURFACE, Card
from tempestweb._core.widgets import Container, PageView, Text

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
