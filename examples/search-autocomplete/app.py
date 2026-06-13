"""Search with autocomplete — exercises Autocomplete, Chip, and dynamic filtering.

A realistic country-search widget: as the user types, the
:class:`~tempestweb._core.widgets.Autocomplete` widget narrows the suggestion
list in real time. Selecting a suggestion commits it as the active choice and
shows it as a :class:`~tempestweb._core.components.Chip` below the field. The
user can clear the committed choice with a button and start over.

The demo also showcases *category filtering*: three
:class:`~tempestweb._core.components.Chip` pills let the user restrict suggestions
to a continent (All / Americas / Europe), so the autocomplete's ``options``
list changes whenever the query *or* the category filter changes.

Run in either mode — the ``view`` function is transport-agnostic::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core.style import Edge
from tempestweb._core.widgets.events import SelectEvent, TextChangeEvent

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Chip
from tempestweb._core.widgets import (
    Autocomplete,
    Button,
    Column,
    Row,
    Text,
    Wrap,
)

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
