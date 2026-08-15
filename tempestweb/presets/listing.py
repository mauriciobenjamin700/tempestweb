"""The list page: toolbar, scrollable table with a sticky head, and pagination."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tempest_core import Style, Text, Widget
from tempest_core.components import EmptyState, SearchBar
from tempest_core.style import Edge
from tempest_core.widgets import Button, Row, TextChangeEvent
from tempestweb.presets import roles
from tempestweb.presets.layout import box, page_header
from tempestweb.presets.models import TableColumn

__all__ = ["data_table", "list_page"]

#: A table cell is either ready text or a widget the app built (a badge, a menu).
Cell = str | Widget


def _cell(value: Cell, *, role: str, align: str, key: str) -> Widget:
    """Wrap one cell value in its table-cell container.

    Args:
        value: The cell's text, or a widget to place in the cell.
        role: ``roles.TABLE_CELL`` or ``roles.TABLE_HEADER_CELL``.
        align: The column's alignment, mirrored to ``data-tw-align``.
        key: The widget key.

    Returns:
        The cell container.
    """
    content: Widget = (
        Text(content=value, key=f"{key}-text") if isinstance(value, str) else value
    )
    return box(role, [content], key=key, attrs={"data-tw-align": align})


def data_table(
    *,
    columns: Sequence[TableColumn],
    rows: Sequence[Sequence[Cell]],
    key: str = "tw-table",
) -> Widget:
    """Render a table that scrolls sideways under a header that stays put.

    The table is built here rather than delegated to the core's ``DataTable``
    because the core resolves row and header backgrounds **inline**, and inline
    beats the stylesheet: zebra striping, row hover and a sticky head would all
    be dead rules. These containers carry no inline background, so
    ``client/layouts.js`` owns the look — and a narrow viewport gets a
    horizontally scrolling table instead of a squashed one.

    Args:
        columns: The column definitions, in order.
        rows: One sequence of cells per row, each aligned with ``columns``. A
            cell is a string or a widget.
        key: The key prefix.

    Returns:
        The scroll container wrapping the table.
    """
    head = box(
        roles.TABLE_HEAD,
        [
            _cell(
                column.label,
                role=roles.TABLE_HEADER_CELL,
                align=column.align,
                key=f"{key}-th-{index}",
            )
            for index, column in enumerate(columns)
        ],
        key=f"{key}-head",
    )
    body: list[Widget] = [head]
    for row_index, row in enumerate(rows):
        body.append(
            box(
                roles.TABLE_ROW,
                [
                    _cell(
                        value,
                        role=roles.TABLE_CELL,
                        align=columns[cell_index].align
                        if cell_index < len(columns)
                        else "start",
                        key=f"{key}-td-{row_index}-{cell_index}",
                    )
                    for cell_index, value in enumerate(row)
                ],
                key=f"{key}-tr-{row_index}",
            )
        )
    table = box(roles.TABLE, body, key=key)
    return box(roles.TABLE_SCROLL, [table], key=f"{key}-scroll")


def _search_adapter(
    on_search: Callable[[str], None],
) -> Callable[[TextChangeEvent], None]:
    """Adapt a plain-text search callback to the widget's event callback.

    ``SearchBar`` reports a :class:`~tempest_core.widgets.base.TextChangeEvent`,
    which also carries pattern validity. A list page has no pattern, and a caller
    of this preset should not have to know the event type to filter a table, so
    the text is unwrapped here.

    Args:
        on_search: The caller's callback, taking the new text.

    Returns:
        A callback in the shape the widget expects.
    """

    def forward(event: TextChangeEvent) -> None:
        """Hand the search box's new text to the page's ``on_search``.

        The preset's caller receives a ``str``; the widget emits an event. This
        adapter is the whole reason ``on_search`` can stay event-free in the
        public signature.

        Args:
            event: The search input's change event.
        """
        on_search(event.value)

    return forward


def _pagination(
    *,
    page: int,
    page_count: int,
    on_page: Callable[[int], None],
    key: str,
) -> Widget:
    """Render "página X de Y" between a previous and a next button.

    Both buttons stay rendered at the ends of the range and simply stop calling
    back, so the control does not change width as you page through.

    Args:
        page: The current 1-based page.
        page_count: The total number of pages.
        on_page: Called with the requested 1-based page.
        key: The key prefix.

    Returns:
        The pagination row.
    """

    def go(target: int) -> Callable[[], None]:
        """Build the click handler for one pagination button.

        A factory rather than a loop variable capture: both buttons are created
        in the same scope, so binding ``target`` as a parameter is what keeps
        "previous" and "next" from sharing the last value.

        Args:
            target: The page number this button navigates to.

        Returns:
            The button's ``on_click``.
        """

        def handler() -> None:
            """Navigate, unless the target is out of range or already current.

            The buttons at the ends of the range stay rendered and simply stop
            calling back — that is what keeps the control from changing width
            as the reader pages through.
            """
            if 1 <= target <= page_count and target != page:
                on_page(target)

        return handler

    return Row(
        key=key,
        style=Style(gap=8.0, padding=Edge.symmetric(vertical=8.0, horizontal=0.0)),
        children=[
            Button(label="Anterior", on_click=go(page - 1), key=f"{key}-prev"),
            Text(
                content=f"Página {page} de {page_count}",
                key=f"{key}-label",
                attrs={roles.LAYOUT_ATTR: roles.SUBTITLE},
            ),
            Button(label="Próxima", on_click=go(page + 1), key=f"{key}-next"),
        ],
    )


def list_page(
    *,
    title: str,
    columns: Sequence[TableColumn],
    rows: Sequence[Sequence[Cell]],
    subtitle: str | None = None,
    actions: Sequence[Widget] = (),
    search: str | None = None,
    on_search: Callable[[str], None] | None = None,
    search_placeholder: str = "Buscar…",
    filters: Sequence[Widget] = (),
    page: int = 1,
    page_count: int = 1,
    on_page: Callable[[int], None] | None = None,
    empty_title: str = "Nada por aqui",
    empty_subtitle: str | None = None,
    empty_action: Widget | None = None,
    key: str = "tw-list",
) -> Widget:
    """Build the standard admin listing screen.

    Header, a toolbar with search and filters, the table, and pagination. When
    ``rows`` is empty the table is replaced by an empty state — an empty result
    is a normal outcome, so it gets a designed screen rather than a bare table
    with no lines.

    Args:
        title: The page title.
        columns: The table's columns.
        rows: The rows to show — already filtered and paged by the app. The
            preset never slices data: what you pass is what is drawn.
        subtitle: Optional line under the title.
        actions: Buttons opposite the title ("Novo usuário").
        search: The current search text. ``None`` omits the search box.
        on_search: Called with the new text as the user types. Required for the
            search box to appear.
        search_placeholder: Placeholder for the search box.
        filters: Extra toolbar widgets (selects, chips, a date range).
        page: The current 1-based page.
        page_count: The total number of pages. ``1`` omits the pagination row.
        on_page: Called with the requested page. Required for pagination.
        empty_title: Heading of the empty state.
        empty_subtitle: Supporting line of the empty state.
        empty_action: Optional button in the empty state ("Criar o primeiro").
        key: The key prefix for the page's widgets.

    Returns:
        The list page.
    """
    children: list[Widget] = [
        page_header(
            title=title, subtitle=subtitle, actions=actions, key=f"{key}-header"
        )
    ]

    toolbar_items: list[Widget] = []
    if search is not None and on_search is not None:
        forward = _search_adapter(on_search)
        toolbar_items.append(
            SearchBar(
                value=search,
                placeholder=search_placeholder,
                on_change=forward,
                key=f"{key}-search",
            )
        )
    if filters:
        toolbar_items.append(
            Row(key=f"{key}-filters", style=Style(gap=8.0), children=list(filters))
        )
    if toolbar_items:
        children.append(box(roles.TOOLBAR, toolbar_items, key=f"{key}-toolbar"))

    if rows:
        children.append(data_table(columns=columns, rows=rows, key=f"{key}-table"))
        if page_count > 1 and on_page is not None:
            children.append(
                _pagination(
                    page=page,
                    page_count=page_count,
                    on_page=on_page,
                    key=f"{key}-pagination",
                )
            )
    else:
        children.append(
            EmptyState(
                title=empty_title,
                subtitle=empty_subtitle,
                action=empty_action,
                key=f"{key}-empty",
            )
        )
    return box(roles.PAGE, children, key=key)
