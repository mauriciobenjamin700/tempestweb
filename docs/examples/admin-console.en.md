# Admin Console (presets)

> 🚀 **What you will build:** a whole admin panel — a shell with a collapsible
> sidebar, a KPI dashboard, a listing with search and pagination, and a settings
> screen — by **describing the data**, without writing a single `Style`, font
> size or breakpoint. Responsive for free.

---

## Why this example matters

This is the same panel as the [Dashboard App Shell](dashboard-shell.md) example,
written the other way round.

| | Dashboard App Shell | Admin Console |
|---|---|---|
| Lines of `app.py` | **716** | **261** |
| Decides spacing, font, colour | you | the preset |
| Responsive | no — fixed widths | yes, with no code of yours |
| What you write | layout widgets | typed records |

The difference is not size, it is **who decides**. In the hand-built shell you
assemble `Scaffold` + `Sidebar` + `Grid` and pick every `padding`, every
`font_size`, every active-item `Color` — and repeat those choices on every
screen. Here you say *which* entries the menu has, *which* KPIs the screen
shows, *which* columns the table has; the preset decides how it looks.

!!! question "Which of the two do I use?"
    **Presets** when the screen is an admin-panel archetype — which is most
    internal screens. **By hand** when the layout is specific to your product and
    no preset describes it. Both use the same core widgets and coexist in one
    app: you can pass a widget of your own as a `Section`'s `body`.

In this tutorial you will learn to:

- Assemble the shell with `admin_shell` — header, collapsible sidebar, content area;
- Describe a dashboard with `dashboard_page`, `Kpi` and `Section`;
- Describe a listing with `list_page`, `TableColumn`, search and pagination;
- Describe a form with `settings_page`, `FormSection` and `FormField`;
- Understand why a preset **never filters or paginates your data**.

!!! note "Runs in both interactive modes, unchanged"
    The same `view()` runs under WASM (Pyodide in the browser) and under Server
    (FastAPI + WebSocket). Responsiveness comes from `client/layouts.js`, which
    is the same JS client in both cases.

!!! warning "Presets do not reach Mode C yet"
    The transpiler only accepts imports from `tempest_core` and
    `tempestweb.native`. A `build --mode transpile` of this example stops right
    there, with the exact line:

    ```text
    tempestweb build: transpile failed: app.py:23: import from
    'tempestweb.presets' is not supported (only tempest_core and `tempestweb.native`)
    ```

    That is why the gallery badge is **[A/B]** and not [A/B/C]. If the screen has
    to be a static bundle, build it from core widgets — that is what the
    [Mode C tour](transpile-tour.md) shows.

## Prerequisites

```bash
pip install tempestweb
```

No extra is needed for Mode A. For Mode B, `pip install "tempestweb[server]"`.

## Project structure

```text
admin-console/
└── app.py        # all of it — 261 lines
```

One file. No CSS, no `styles/`, no theme tokens: the preset emits role markers
(`data-tw-layout`) and the client's responsive sheet resolves the appearance.

## Step 1 — The records that describe the screen

Presets do not take layout widgets, they take **typed records**:

```python
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
```

`NavItem(label, value, badge=...)` — `value` is what reaches your `on_navigate`.
`badge` is optional and becomes the trailing counter next to the label.

State is a plain dataclass:

```python
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
```

!!! tip "Tip — `sidebar_open` is yours, not the preset's"
    The preset draws the sidebar open or closed according to the `bool` you pass,
    and calls `on_toggle_sidebar` when the user taps the burger. It stores no
    state at all. That is the rule for every preset: they **render**, the app
    **decides**.

## Step 2 — The dashboard: `Kpi` + `Section`

```python
def _overview() -> Widget:
    """Build the dashboard screen."""
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
```

You wrote no column count. The KPI grid is
`repeat(auto-fit, minmax(…, 1fr))`: as many cards fit as the available width
allows — four on a 1440px screen, one on a 390px phone — and the number changes
by itself as the window does. `tone` is `"neutral"` (the default), `"success"`,
`"warning"` or `"danger"`, and `up=False` flips the delta arrow without touching
the colour.

`Section(title, body, subtitle=..., span=...)` is the content card. `body` is
**any widget** — a core `LineChart` here, a `Text` there. `span="full"` makes the
section take the whole grid row.

!!! info "Info — the preset does not know what a chart is"
    `Section` takes a `Widget` and draws it inside the card. That is what keeps
    presets useful: the archetype covers the frame, and the filling stays the
    entire `tempest_core` catalogue.

## Step 3 — The listing: `list_page`

```python
def _users(app: App[State]) -> Widget:
    """Build the user listing screen."""

    def search(text: str) -> None:
        app.set_state(lambda s: (setattr(s, "query", text), setattr(s, "page", 1))[0])

    def go(page: int) -> None:
        app.set_state(lambda s: setattr(s, "page", page))

    rows = _matching(app.state.query)
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
            for name, email, role, balance in rows
        ],
        search=app.state.query,
        on_search=search,
        actions=[Button(label="Novo usuário", on_click=lambda: None, key="new-user")],
        page=app.state.page,
        page_count=2,
        on_page=go,
        empty_title="Nenhum usuário encontrado",
        empty_subtitle="Ajuste a busca ou convide alguém para a equipe.",
    )
```

A cell in `rows` is a **string or a widget** — note the `Badge` in the third
column. `TableColumn("Saldo", align="end")` right-aligns the whole column,
header included. `empty_title`/`empty_subtitle` only show when `rows` is empty;
you do not write the `if`.

!!! warning "Warning — the preset does **not** filter or paginate your data"
    `search=` and `page=` are **displayed values**, not instructions. Slicing the
    list is your job:

    ```python
    def _matching(query: str) -> list[tuple[str, str, str, str]]:
        """Filter the user list by name or email."""
        needle = query.strip().lower()
        if not needle:
            return USERS
        return [
            row for row in USERS if needle in row[0].lower() or needle in row[1].lower()
        ]
    ```

    This is deliberate. In the real world the search usually becomes a `WHERE` in
    the database or an API parameter, not an in-memory filter — a preset that
    "filtered by itself" would only work in the toy case. Note too that
    `search()` resets `page` to `1`: changing the filter without resetting the
    page is the classic bug on this screen.

## Step 4 — The form: `settings_page`

```python
    return settings_page(
        title="Ajustes",
        subtitle="Preferências da organização",
        sections=[
            FormSection(
                "Organização",
                [
                    FormField(
                        "Razão social",
                        Input(value=app.state.company, on_change=set_company, key="company"),
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
```

`FormField(label, control, help=..., error=..., span=...)`. The label, the help
text and the error line come out positioned and in the right colour; a non-empty
`error` swaps the colour and shows the line. `span="full"` makes the field take
the section's full width.

!!! tip "Tip — `form_page` and `settings_page` render the same"
    `settings_page` **is** `form_page` with the narrower signature: it only takes
    `sections`, never loose fields. Use `form_page` when the screen is a simple
    form (`fields=[...]` in a single grid) and `settings_page` when the fields
    always belong to a group. The visual result is the same — the difference is
    what the type lets you write.

    The action bar is right-aligned on desktop and **stacks on a phone with the
    last action of the list on top** (`flex-direction: column-reverse`). Put the
    primary action last in `actions=`, as the example does with
    `[Cancelar, Salvar]`.

## Step 5 — The shell that stitches it together

```python
def view(app: App[State]) -> Widget:
    """Render the console."""

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
        footer=Text(content="ana@acme.com", key="signed-in", style=Style(font_size=12.0)),
        body=bodies[app.state.tab](),
    )
```

A `dict` of functions and a `str` in the state — that is the whole "navigation".
`body` is the result of the active screen.

!!! tip "Tip — close the drawer when navigating"
    Note that `navigate` also writes `sidebar_open = False`. On a phone the
    sidebar is an overlaid drawer; without that line it stays open on top of the
    content the user just asked for.

## Step 6 — Run it

```bash
tempestweb dev --mode server --path examples/admin-console   # Mode B
tempestweb dev --mode wasm   --path examples/admin-console   # Mode A
```

What you see on desktop (≥1024px): sidebar pinned left, KPIs across four
columns, the chart section taking the row, the table with a sticky header.

On a phone (≤430px): the sidebar becomes a drawer behind a burger in the header,
the KPIs stack, the form drops to one column, the action bar stacks with the
primary action on top, and the table scrolls horizontally inside its own card —
the page itself never scrolls sideways.

!!! check "Verified in the browser"
    The behaviours above were checked in Chromium against the real Mode B, at
    1440×900 and 390×844: burger absent on desktop and present on mobile, drawer
    with a scrim, auto-close on navigate, table with its own scroll, search
    round-tripping over the WebSocket (`5 de 5` → `1 de 5`), and zero console
    messages.

## Recap

In this tutorial you assembled a whole admin panel and learned:

- 💡 **`admin_shell`** delivers header + collapsible sidebar + content area; the
  open/closed `bool` is yours.
- 💡 **`dashboard_page`** takes `Kpi` and `Section` — column count and
  breakpoints are not your decision.
- 💡 **`list_page`** delivers a search toolbar, table, pagination and empty
  state; a cell can be a widget.
- 💡 **`settings_page`** positions label, help and error from a `FormField`.
- 💡 The preset **renders, the app decides**: filtering, paginating and
  validating stay your code — which is why the same screen works against a
  `WHERE` in a database.
- 💡 **261 lines** against **716** for the same panel built by hand, and those
  261 are responsive.

---

## Next steps

- Read [Ready-made screens (presets)](../tutorial/presets.md) for the reference of all
  five presets and every record.
- Compare with the [Dashboard App Shell](dashboard-shell.md), the same panel
  assembled widget by widget.
- See [Ready-made components](../tutorial/components.md) for the catalogue you use inside
  a `Section`.
