"""The admin shell: header, collapsible sidebar and a scrolling content area."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tempest_core import Style, Widget
from tempest_core.components import AppBar
from tempest_core.components.base import ACCENT, ON_MUTED, SURFACE
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.widgets import Button, Column
from tempest_core.widgets.base import Semantics
from tempestweb.presets import roles
from tempestweb.presets.layout import box, muted
from tempestweb.presets.models import NavItem

__all__ = ["admin_shell"]

#: Fully transparent, for a nav entry that is not the current one. The core
#: resolves a Button's fill inline, so "no background" has to be said explicitly.
_TRANSPARENT = Color(r=0, g=0, b=0, a=0.0)

#: Text on the accent fill. Accent is the one colour that reads the same on the
#: shell's dark chrome and on a light header, so the two controls that must be
#: visible in both — the current nav entry and the burger — share it.
_ON_ACCENT = Color(r=255, g=255, b=255, a=1.0)


def _nav_button(
    item: NavItem,
    *,
    active: bool,
    on_navigate: Callable[[str], None],
) -> Widget:
    """Render one sidebar entry.

    Args:
        item: The entry to render.
        active: Whether this entry is the current one.
        on_navigate: Called with the entry's ``value`` when it is chosen.

    Returns:
        A full-width button tagged as a nav item, marked ``data-tw-active`` when
        current so the sheet (and a reader of the DOM) can tell.
    """

    def choose() -> None:
        """Report this nav entry's ``value`` to the shell's ``on_navigate``.

        The app receives the entry's value, never the widget or the label, so a
        rename of the visible text cannot change which screen a click selects.
        """
        on_navigate(item.value)

    label = f"{item.label}  ({item.badge})" if item.badge is not None else item.label
    return Button(
        label=label,
        on_click=choose,
        key=f"tw-nav-{item.value}",
        attrs={
            roles.LAYOUT_ATTR: roles.NAV_ITEM,
            "data-tw-active": str(active).lower(),
        },
        style=Style(
            padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
            radius=8.0,
            background=ACCENT if active else _TRANSPARENT,
            color=_ON_ACCENT if active else ON_MUTED,
            font_size=14.0,
            font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
        ),
    )


def admin_shell(
    *,
    title: str,
    nav: Sequence[NavItem],
    active: str,
    on_navigate: Callable[[str], None],
    body: Widget,
    brand: str | None = None,
    actions: Sequence[Widget] = (),
    footer: Widget | None = None,
    sidebar_open: bool = False,
    on_toggle_sidebar: Callable[[], None] | None = None,
    key: str = "tw-shell",
) -> Widget:
    """Build an admin shell around ``body``.

    The layout is a grid: the sidebar owns a column and the header a row, so the
    content area never needs a margin kept in sync with the sidebar's width.
    Below 1024px the sidebar leaves the grid and becomes an overlay — pass
    ``sidebar_open`` and ``on_toggle_sidebar`` to drive it, and the burger button
    appears (the sheet hides it on wide screens, where the sidebar is permanent).

    Nothing here measures the viewport: every breakpoint lives in
    ``client/layouts.js``. The same tree is correct at any width.

    Args:
        title: The application title, shown in the header.
        nav: The sidebar entries.
        active: The ``value`` of the current entry, matched against ``nav``.
        on_navigate: Called with an entry's ``value`` when it is chosen.
        body: The content area — usually a page preset.
        brand: Optional product name shown above the nav.
        actions: Widgets pinned to the right of the header (a user menu, a
            "Sair" button).
        footer: Optional widget pinned under the nav (the signed-in user).
        sidebar_open: Whether the overlay sidebar is open. Ignored on wide
            screens, where the sidebar is always visible.
        on_toggle_sidebar: Called when the burger or the scrim is tapped. Pass
            ``None`` when the app has no small-screen story and the burger is
            omitted.
        key: The key prefix for the shell's widgets.

    Returns:
        The shell widget tree.
    """
    open_flag = "true" if sidebar_open else "false"

    nav_children: list[Widget] = []
    if brand is not None:
        nav_children.append(
            Column(
                key=f"{key}-brand",
                style=Style(padding=Edge.all(16.0)),
                children=[muted(brand, key=f"{key}-brand-text")],
            )
        )
    nav_children.append(
        Column(
            key=f"{key}-nav",
            style=Style(gap=4.0, padding=Edge.symmetric(vertical=8.0, horizontal=8.0)),
            children=[
                _nav_button(item, active=item.value == active, on_navigate=on_navigate)
                for item in nav
            ],
        )
    )
    if footer is not None:
        nav_children.append(
            Column(
                key=f"{key}-footer",
                style=Style(padding=Edge.all(16.0)),
                children=[footer],
            )
        )

    header_actions: list[Widget] = list(actions)
    leading: Widget | None = None
    if on_toggle_sidebar is not None:
        leading = Button(
            label="☰",
            on_click=on_toggle_sidebar,
            key=f"{key}-burger",
            semantics=Semantics(label="Abrir menu"),
            attrs={roles.LAYOUT_ATTR: roles.SHELL_BURGER},
            style=Style(
                padding=Edge.symmetric(vertical=8.0, horizontal=12.0),
                radius=8.0,
                background=ACCENT,
                color=_ON_ACCENT,
            ),
        )

    children: list[Widget] = [
        box(
            roles.SHELL_SIDEBAR,
            nav_children,
            key=f"{key}-sidebar",
            attrs={"data-tw-open": open_flag},
            style=Style(background=SURFACE),
        ),
        box(
            roles.SHELL_HEADER,
            [
                AppBar(
                    title=title,
                    leading=leading,
                    actions=header_actions,
                    key=f"{key}-appbar",
                )
            ],
            key=f"{key}-header",
        ),
        box(roles.SHELL_MAIN, [body], key=f"{key}-main"),
    ]
    if on_toggle_sidebar is not None:
        children.append(
            _scrim(key=f"{key}-scrim", open_flag=open_flag, on_close=on_toggle_sidebar)
        )
    return box(roles.SHELL, children, key=key)


def _scrim(*, key: str, open_flag: str, on_close: Callable[[], None]) -> Widget:
    """Render the backdrop that closes the overlay sidebar when tapped.

    The sheet keeps it display:none until both the viewport is narrow and
    ``data-tw-open`` is true, so on a desktop it never covers anything.

    Args:
        key: The widget key.
        open_flag: ``"true"``/``"false"`` mirroring the sidebar's state.
        on_close: Called when the backdrop is tapped.

    Returns:
        The scrim container.
    """
    return box(
        roles.SHELL_SCRIM,
        [
            Button(
                label="",
                on_click=on_close,
                key=f"{key}-close",
                semantics=Semantics(label="Fechar menu"),
                style=Style(
                    grow=1.0,
                    background=_TRANSPARENT,
                    radius=0.0,
                    padding=Edge.all(0.0),
                ),
            )
        ],
        key=key,
        attrs={"data-tw-open": open_flag},
    )
