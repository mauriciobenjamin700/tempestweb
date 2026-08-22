# Ready-made screens (presets)

!!! abstract "What you will learn"
    How to build a whole admin panel — shell with a sidebar, a KPI dashboard, a
    searchable paginated list, a form and a sign-in screen — by **describing the
    data**, without writing a single `Style`, font size or breakpoint. And how
    the layout becomes responsive for free. 🚀

## The problem

tempestweb already ships components: `Card`, `DataTable`, `StatCard`, `AppBar`,
`EmptyState`… Assembling a panel out of them is still work — the
[`dashboard-shell`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/examples/dashboard-shell)
example spends **716 lines** deciding spacing, font sizes, the active item's
colour and how many columns the grid has.

Worse: none of it adapts. Inline `Style` has no media query, so a hand-built
layout is fixed-width by construction.

**Presets** fix both: you say *what* is on the screen, they decide *how* it
looks.

=== "With a preset"

    ```python
    from tempestweb.presets import Kpi, NavItem, admin_shell, dashboard_page


    def view(app: App[State]) -> Widget:
        return admin_shell(
            title="ACME Console",
            nav=[NavItem("Overview", "overview"), NavItem("Users", "users")],
            active=app.state.tab,
            on_navigate=lambda value: app.set_state(lambda s: setattr(s, "tab", value)),
            body=dashboard_page(
                title="Overview",
                kpis=[
                    Kpi("Revenue", "$82.4k", delta="+12%", tone="success"),
                    Kpi("Churn", "1.8%", delta="-0.3%", up=False, tone="warning"),
                ],
            ),
        )
    ```

=== "By hand"

    ```python
    return Scaffold(
        app_bar=AppBar(title="ACME Console", ...),
        sidebar=Sidebar(children=[
            Button(label="Overview", on_click=..., style=Style(
                padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                radius=8.0, background=ACCENT if active else ...,
                color=..., font_size=14.0, font_weight=...,
            )),
            # … repeated per item, and again on every screen
        ]),
        body=Column(style=Style(gap=24.0, padding=Edge.all(24.0)), children=[
            Text(content="Overview", style=Style(font_size=24.0, ...)),
            Grid(columns=4, children=[...]),   # a hard 4: breaks on a phone
        ]),
    )
    ```

## The five presets

| Preset | What it gives you |
|---|---|
| `admin_shell` | Header + collapsible sidebar + content area |
| `dashboard_page` | A KPI row over a grid of sections |
| `list_page` | Toolbar with search, table, pagination, empty state |
| `form_page` / `settings_page` | Labelled fields in a grid + an action bar |
| `auth_page` | A centred card wrapping your own form |

!!! info "`form_page` or `settings_page`?"
    Both draw **the same screen**. The difference is the signature:
    `settings_page` only takes `sections` — fields always grouped — while
    `form_page` also takes loose `fields`. Pass both and the loose ones come
    first, in their own grid.

    Use `form_page` for a simple form ("create record") and `settings_page` when
    the fields always belong to a group. The key prefix differs too (`tw-form`
    vs `tw-settings`), so the two kinds of screen keep distinct keys.

    The action bar is right-aligned on desktop and **stacks on a phone with the
    last action of the list on top** — put the primary action last in
    `actions=`.

Each takes **typed records**, not layout widgets:

```python
from tempestweb.presets import (
    FormField, FormSection, Kpi, NavItem, Section, TableColumn,
)
```

## A complete app

```python
from dataclasses import dataclass

from tempest_core import App, Text, Widget
from tempest_core import Button
from tempestweb.presets import (
    Kpi, NavItem, Section, TableColumn, admin_shell, dashboard_page, list_page,
)

USERS = [("Ana", "ana@acme.com", "$12,400"), ("Bruno", "bruno@acme.com", "$8,900")]


@dataclass
class State:
    tab: str = "overview"
    sidebar_open: bool = False
    query: str = ""


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    def navigate(value: str) -> None:
        app.set_state(lambda s: (setattr(s, "tab", value), setattr(s, "sidebar_open", False))[0])

    def toggle() -> None:
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    def search(text: str) -> None:
        app.set_state(lambda s: setattr(s, "query", text))

    if app.state.tab == "overview":
        body = dashboard_page(
            title="Overview",
            subtitle="Last 30 days",
            kpis=[
                Kpi("Revenue", "$82.4k", delta="+12%", tone="success"),
                Kpi("Active users", "1,284", delta="+4%", tone="success"),
                Kpi("Churn", "1.8%", delta="-0.3%", up=False, tone="warning"),
            ],
            sections=[Section("Notes", Text(content="No incidents.", key="n"))],
        )
    else:
        rows = [r for r in USERS if app.state.query.lower() in r[0].lower()]
        body = list_page(
            title="Users",
            columns=[TableColumn("Name"), TableColumn("Email"), TableColumn("Balance", align="end")],
            rows=[list(row) for row in rows],
            search=app.state.query,
            on_search=search,
            actions=[Button(label="New user", on_click=lambda: None, key="new")],
            empty_title="No users found",
        )

    return admin_shell(
        title="ACME Console",
        brand="ACME",
        nav=[NavItem("Overview", "overview"), NavItem("Users", "users", badge="3")],
        active=app.state.tab,
        on_navigate=navigate,
        sidebar_open=app.state.sidebar_open,
        on_toggle_sidebar=toggle,
        body=body,
    )
```

Run it with `tempestweb dev --mode server` (or `--mode wasm`) and you get: a
pinned sidebar on desktop, a drawer with a scrim on a phone, KPIs that reflow, a
table with a sticky header and sideways scrolling, zebra rows — without a line
of CSS.

!!! check "Nothing here measures the screen"
    There is no `if width < 768` in your code or in the presets'. The
    breakpoints live in `client/layouts.js`, the sheet the client injects at
    mount. **The same tree is correct at every width**, in all three modes.

## What the sheet gives you

| Behaviour | Where it shows up |
|---|---|
| Sidebar becomes an overlay drawer below 1024px | `admin_shell` |
| The ☰ button appears only where the sidebar is a drawer | `admin_shell` |
| A scrim that closes the drawer when tapped | `admin_shell` |
| KPIs reflow 4 → 3 → 2 → 1 with the width | `dashboard_page` |
| Sections in a grid, `span="full"` taking the row | `dashboard_page` |
| Table scrolls sideways under a sticky header | `list_page` |
| Zebra striping and row hover | `list_page` |
| Fields in a grid, one column on a phone | `form_page` |
| Stacked action bar (primary action last) | `form_page` |
| Sign-in card centred and capped at 420px | `auth_page` |
| Printing without sidebar, header or buttons | all |
| `prefers-reduced-motion` drops the drawer animation | `admin_shell` |

## How it works underneath

Each preset stamps `data-tw-layout="<role>"` on the containers it owns, through
the core's `attrs` escape hatch. The sheet matches its rules on that attribute:

```html
<div data-tw-layout="shell">
  <div data-tw-layout="shell-sidebar" data-tw-open="false">…</div>
  <div data-tw-layout="shell-header">…</div>
  <div data-tw-layout="shell-main">
    <div data-tw-layout="page">…</div>
  </div>
</div>
```

The role vocabulary is **closed** and lives in `tempestweb/presets/roles.py`;
tests fail if the sheet styles a role nobody emits or a role has no rule. You do
not need to (and should not) stamp these attributes by hand — they come from
using a preset.

!!! warning "Inline Style always wins"
    Nothing in the sheet uses `!important`. Set a `Style` on a widget and your
    value wins — the sheet is a floor, not a cage. The flip side: a widget that
    **already** has an inline colour (every `Button` does, resolved by the core's
    variant) cannot be recoloured by the sheet. That is why a nav item's hover
    cue is a `filter` rather than a `background`.

## Customising

The presets read CSS tokens you can override from your own `<style>`:

```html
<style>
  :root {
    --tw-layout-sidebar-width: 300px;
    --tw-layout-content-max: 1440px;
    --tw-layout-page-padding: 32px;
    --tw-layout-kpi-min: 240px;   /* wider KPIs = fewer columns */
    --tw-primary: #0b57d0;        /* base-theme token, inherited by headings */
  }
</style>
```

Need more? The presets compose the **same public components** you would. Swap
just the part you care about:

```python
admin_shell(
    ...,
    body=my_hand_built_screen(app),   # keep the shell, own the content
)
```

## Recap

- **You describe, the preset draws.** `NavItem`, `Kpi`, `Section`,
  `TableColumn`, `FormField` — data, not layout.
- **Responsive with no media query of yours.** It all lives in
  `client/layouts.js`, wired by `data-tw-layout`.
- **No dead ends.** Inline `Style` still wins, tokens rebrand the sheet, and any
  region takes a widget of your own instead.

!!! warning "Modes A and B — presets do not transpile"
    The Mode C compiler only accepts imports from `tempest_core` and
    `tempestweb.native`. An app that imports `tempestweb.presets` stops at
    `build --mode transpile`, with `file:line`:

    ```text
    tempestweb build: transpile failed: app.py:23: import from
    'tempestweb.presets' is not supported (only tempest_core and `tempestweb.native`)
    ```

    Presets target internal panels and signed-in apps, where Mode B is the
    natural choice. A public screen that needs a static bundle is still built
    from core widgets.

Full example, walked through step by step:
[**Admin Console**](../examples/admin-console.md) — the same screens as
[`dashboard-shell`](../examples/dashboard-shell.md) in 261 lines instead of 716.

!!! info "API reference"
    Every preset's and record's signature: [`tempestweb.presets`](../reference/presets.md).
