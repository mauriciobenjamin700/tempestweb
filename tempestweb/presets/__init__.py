"""Ready-made screens for dashboards, admin panels and internal tools.

A preset is a whole screen you describe with data instead of assembling with
widgets. You say *what* is on it — these nav entries, these KPIs, these columns,
these fields — and the preset decides the spacing, the type scale, the grid and
the responsive behaviour::

    from tempestweb.presets import Kpi, NavItem, admin_shell, dashboard_page

    def view(app):
        return admin_shell(
            title="Painel",
            nav=[NavItem("Visão geral", "overview"), NavItem("Usuários", "users")],
            active=app.state.tab,
            on_navigate=lambda value: app.set_state(...),
            body=dashboard_page(
                title="Visão geral",
                kpis=[Kpi("Receita", "R$ 82k", delta="+12%", tone="success")],
            ),
        )

**Nothing here measures the viewport.** Every breakpoint lives in
``client/layouts.js``, the stylesheet the client injects at mount: the sidebar
collapses under 1024px, the KPI row reflows, the table scrolls sideways under a
sticky header, and printing drops the chrome. The presets only tag each
container with its layout role (``data-tw-layout``) so those rules can find it.
That means the same tree is correct at every width, in all three modes, with no
media query of your own — and an inline ``Style`` you set still wins over
anything the sheet says.

The presets compose the same public components an app would: they are a
shortcut, never a wall. Use one for the shell and hand-build the body, replace a
section with your own widget, or stop using them entirely — the widgets
underneath are the ones you already know.
"""

from __future__ import annotations

from tempestweb.presets.auth import auth_page
from tempestweb.presets.dashboard import dashboard_page, kpi_grid, section_grid
from tempestweb.presets.forms import form_page, form_section, settings_page
from tempestweb.presets.layout import box, heading, muted, page_header
from tempestweb.presets.listing import data_table, list_page
from tempestweb.presets.models import (
    Align,
    FormField,
    FormSection,
    Kpi,
    NavItem,
    Section,
    Span,
    TableColumn,
    Tone,
)
from tempestweb.presets.roles import LAYOUT_ATTR, ROLES
from tempestweb.presets.shell import admin_shell

__all__ = [
    "LAYOUT_ATTR",
    "ROLES",
    "Align",
    "FormField",
    "FormSection",
    "Kpi",
    "NavItem",
    "Section",
    "Span",
    "TableColumn",
    "Tone",
    "admin_shell",
    "auth_page",
    "box",
    "dashboard_page",
    "data_table",
    "form_page",
    "form_section",
    "heading",
    "kpi_grid",
    "list_page",
    "muted",
    "page_header",
    "section_grid",
    "settings_page",
]
