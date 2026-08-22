"""Admin console — the same screens as `dashboard-shell`, built from presets.

Where ``examples/dashboard-shell`` assembles the chrome by hand (716 lines of
cards, nav buttons and grids), this app *describes* it: nav entries, KPIs,
sections, table columns and form fields. ``tempestweb.presets`` turns that into
the tree, and ``client/layouts.js`` makes it responsive — the sidebar collapses
under 1024px, the grids reflow, the table scrolls under a sticky header. There
is not one font size or breakpoint in this file.

Both modes run this exact ``view`` unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from tempest_core import App, Style, Text, Widget
from tempest_core.components import Badge, ChartSeries, LineChart
from tempest_core.widgets import Button, Input
from tempestweb.presets import (
    FormField,
    FormSection,
    Kpi,
    NavItem,
    Section,
    TableColumn,
    admin_shell,
    dashboard_page,
    list_page,
    settings_page,
)

NAV: list[NavItem] = [
    NavItem("Visão geral", "overview"),
    NavItem("Usuários", "users", badge="3"),
    NavItem("Ajustes", "settings"),
]

USERS: list[tuple[str, str, str, str]] = [
    ("Ana Souza", "ana@acme.com", "Admin", "R$ 12.400"),
    ("Bruno Lima", "bruno@acme.com", "Editor", "R$ 8.900"),
    ("Carla Dias", "carla@acme.com", "Leitor", "R$ 3.100"),
    ("Diego Reis", "diego@acme.com", "Editor", "R$ 15.750"),
    ("Elisa Nunes", "elisa@acme.com", "Admin", "R$ 22.030"),
]


@dataclass
class State:
    """Application state."""

    tab: str = "overview"
    sidebar_open: bool = False
    query: str = ""
    page: int = 1
    company: str = "ACME Ltda"
    notify: str = "diário"
    errors: dict[str, str] = field(default_factory=dict)


def make_state() -> State:
    """Build the initial state.

    Returns:
        A fresh :class:`State`.
    """
    return State()


def _matching(query: str) -> list[tuple[str, str, str, str]]:
    """Filter the user list by name or email.

    Filtering is the app's job — a preset draws the rows it is handed and never
    slices data itself.

    Args:
        query: The current search text.

    Returns:
        The matching rows, or all of them when the query is empty.
    """
    needle = query.strip().lower()
    if not needle:
        return USERS
    return [
        row for row in USERS if needle in row[0].lower() or needle in row[1].lower()
    ]


def _overview() -> Widget:
    """Build the dashboard screen.

    Returns:
        The dashboard page.
    """
    return dashboard_page(
        title="Visão geral",
        subtitle="Últimos 30 dias",
        kpis=[
            Kpi("Receita", "R$ 82.400", delta="+12%", tone="success"),
            Kpi("Usuários ativos", "1.284", delta="+4%", tone="success"),
            Kpi("Churn", "1,8%", delta="-0,3%", up=False, tone="warning"),
            Kpi("Chamados abertos", "17", delta="+5", tone="danger"),
        ],
        sections=[
            Section(
                "Receita por semana",
                LineChart(
                    key="revenue",
                    series=[
                        ChartSeries(label="2026", points=[12.0, 18.0, 15.0, 22.0, 28.0])
                    ],
                ),
                subtitle="Em milhares de reais",
                span="full",
            ),
            Section("Notas", Text(content="Sem incidentes na semana.", key="notes")),
        ],
    )


#: Rows per page in the user listing.
PAGE_SIZE: int = 3


def _users(app: App[State]) -> Widget:
    """Build the user listing screen.

    Args:
        app: The application handle.

    Returns:
        The list page.
    """

    def search(text: str) -> None:
        app.set_state(lambda s: (setattr(s, "query", text), setattr(s, "page", 1))[0])

    def go(page: int) -> None:
        app.set_state(lambda s: setattr(s, "page", page))

    rows = _matching(app.state.query)
    # Page the rows for real. Passing every row with a hard-coded page_count made
    # the pager decorative: "Próxima" moved the label to "Página 2 de 2" and left
    # the same five rows on screen.
    page_count = max(1, ceil(len(rows) / PAGE_SIZE))
    page = min(max(app.state.page, 1), page_count)
    window = rows[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    return list_page(
        title="Usuários",
        subtitle=f"{len(rows)} de {len(USERS)}",
        columns=[
            TableColumn("Nome"),
            TableColumn("Email"),
            TableColumn("Papel"),
            TableColumn("Saldo", align="end"),
        ],
        rows=[
            [name, email, Badge(label=role, tone="info", key=f"role-{email}"), balance]
            for name, email, role, balance in window
        ],
        search=app.state.query,
        on_search=search,
        actions=[Button(label="Novo usuário", on_click=lambda: None, key="new-user")],
        page=page,
        page_count=page_count,
        on_page=go,
        empty_title="Nenhum usuário encontrado",
        empty_subtitle="Ajuste a busca ou convide alguém para a equipe.",
    )


def _settings(app: App[State]) -> Widget:
    """Build the settings screen.

    Args:
        app: The application handle.

    Returns:
        The settings page.
    """

    def set_company(event: object) -> None:
        value = str(getattr(event, "value", ""))
        app.set_state(lambda s: setattr(s, "company", value))

    return settings_page(
        title="Ajustes",
        subtitle="Preferências da organização",
        sections=[
            FormSection(
                "Organização",
                [
                    FormField(
                        "Razão social",
                        Input(
                            value=app.state.company,
                            on_change=set_company,
                            key="company",
                        ),
                        help="Aparece nas notas fiscais.",
                    ),
                    FormField(
                        "Domínio",
                        Input(value="acme.com", key="domain"),
                        error=app.state.errors.get("domain"),
                    ),
                ],
                subtitle="Dados usados em documentos e emails.",
            ),
            FormSection(
                "Notificações",
                [
                    FormField(
                        "Resumo por email",
                        Input(value=app.state.notify, key="notify"),
                        help="diário, semanal ou nunca",
                        span="full",
                    )
                ],
            ),
        ],
        actions=[
            Button(label="Cancelar", on_click=lambda: None, key="cancel"),
            Button(label="Salvar", on_click=lambda: None, key="save"),
        ],
    )


def view(app: App[State]) -> Widget:
    """Render the console.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def navigate(value: str) -> None:
        app.set_state(
            lambda s: (setattr(s, "tab", value), setattr(s, "sidebar_open", False))[0]
        )

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    bodies = {
        "overview": _overview,
        "users": lambda: _users(app),
        "settings": lambda: _settings(app),
    }
    return admin_shell(
        title="Console ACME",
        brand="ACME",
        nav=NAV,
        active=app.state.tab,
        on_navigate=navigate,
        sidebar_open=app.state.sidebar_open,
        on_toggle_sidebar=toggle,
        actions=[Button(label="Sair", on_click=lambda: None, key="logout")],
        footer=Text(
            content="ana@acme.com",
            key="signed-in",
            style=Style(font_size=12.0),
        ),
        body=bodies[app.state.tab](),
    )
