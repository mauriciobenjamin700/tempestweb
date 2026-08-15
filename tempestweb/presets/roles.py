"""The layout-role vocabulary shared with ``client/layouts.js``.

A preset tags each container it owns with ``data-tw-layout="<role>"`` (through
the core's ``attrs`` escape hatch), and the stylesheet keys every rule off those
roles. The vocabulary is **closed**: this module is the single source of truth,
and ``tests/unit/test_presets_roles.py`` fails when a role here has no rule in
the sheet or the sheet styles a role that no longer exists — the two halves of
the feature cannot drift apart silently.

Apps are not meant to stamp these attributes by hand. They come from using a
preset; the roles are documented so a reader of the DOM (or of the sheet) can
tell what a container is for.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "AUTH",
    "AUTH_CARD",
    "FORM_ACTIONS",
    "FORM_FIELD",
    "FORM_GRID",
    "KPI_GRID",
    "LAYOUT_ATTR",
    "NAV_ITEM",
    "PAGE",
    "PAGE_ACTIONS",
    "PAGE_HEADER",
    "ROLES",
    "SECTION",
    "SECTION_GRID",
    "SHELL",
    "SHELL_BURGER",
    "SHELL_HEADER",
    "SHELL_MAIN",
    "SHELL_SCRIM",
    "SHELL_SIDEBAR",
    "TABLE",
    "TABLE_CELL",
    "TABLE_HEADER_CELL",
    "TABLE_HEAD",
    "TABLE_ROW",
    "TOOLBAR",
]

#: The attribute every preset stamps to name a container's layout role.
LAYOUT_ATTR: Final[str] = "data-tw-layout"

SHELL: Final[str] = "shell"
SHELL_HEADER: Final[str] = "shell-header"
SHELL_SIDEBAR: Final[str] = "shell-sidebar"
SHELL_MAIN: Final[str] = "shell-main"
SHELL_SCRIM: Final[str] = "shell-scrim"
SHELL_BURGER: Final[str] = "shell-burger"
NAV_ITEM: Final[str] = "nav-item"

PAGE: Final[str] = "page"
PAGE_HEADER: Final[str] = "page-header"
PAGE_ACTIONS: Final[str] = "page-actions"
TOOLBAR: Final[str] = "toolbar"

KPI_GRID: Final[str] = "kpi-grid"
SECTION_GRID: Final[str] = "section-grid"
SECTION: Final[str] = "section"

TABLE: Final[str] = "table"
TABLE_SCROLL: Final[str] = "table-scroll"
TABLE_HEAD: Final[str] = "table-head"
TABLE_ROW: Final[str] = "table-row"
TABLE_CELL: Final[str] = "table-cell"
TABLE_HEADER_CELL: Final[str] = "table-header-cell"

FORM_GRID: Final[str] = "form-grid"
FORM_FIELD: Final[str] = "form-field"
FORM_ACTIONS: Final[str] = "form-actions"

AUTH: Final[str] = "auth"
AUTH_CARD: Final[str] = "auth-card"

#: Every role the presets emit, for the drift guard against ``layouts.js``.
ROLES: Final[frozenset[str]] = frozenset(
    {
        SHELL,
        SHELL_HEADER,
        SHELL_SIDEBAR,
        SHELL_MAIN,
        SHELL_SCRIM,
        SHELL_BURGER,
        NAV_ITEM,
        PAGE,
        PAGE_HEADER,
        PAGE_ACTIONS,
        TOOLBAR,
        KPI_GRID,
        SECTION_GRID,
        SECTION,
        TABLE,
        TABLE_SCROLL,
        TABLE_HEAD,
        TABLE_ROW,
        TABLE_CELL,
        TABLE_HEADER_CELL,
        FORM_GRID,
        FORM_FIELD,
        FORM_ACTIONS,
        AUTH,
        AUTH_CARD,
    }
)
