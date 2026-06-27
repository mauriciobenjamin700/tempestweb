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

# ---------------------------------------------------------------------------
# FAQ data
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


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

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Filter entries
    # ------------------------------------------------------------------

    query_lower = app.state.query.strip().lower()
    visible: list[tuple[int, str, str]] = [
        (idx, question, answer)
        for idx, (question, answer) in enumerate(_FAQ_ENTRIES)
        if not query_lower
        or query_lower in question.lower()
        or query_lower in answer.lower()
    ]

    # ------------------------------------------------------------------
    # Accordion items
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Footer counter
    # ------------------------------------------------------------------

    total = len(_FAQ_ENTRIES)
    shown = len(visible)
    if query_lower:
        stripped = app.state.query.strip()
        counter_text = f'{shown} of {total} questions match "{stripped}"'
    else:
        counter_text = f"{total} questions"

    # ------------------------------------------------------------------
    # Root tree
    # ------------------------------------------------------------------

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
