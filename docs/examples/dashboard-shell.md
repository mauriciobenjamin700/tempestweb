# Dashboard App Shell

> 🚀 **O que você vai construir:** um shell de dashboard completo com `Scaffold` +
> `AppBar` + `Sidebar` + `NavBar`, quatro seções permutáveis (Overview, Analytics,
> Users, Settings) e estado reativo — tudo em Python puro, sem CSS manual.

---

## Por que esse exemplo importa?

A maioria das aplicações web reais tem a mesma forma: uma barra superior com título e
ações, um menu lateral que organiza as seções, uma barra de navegação inferior para
telas menores e um corpo central que troca de conteúdo sem recarregar a página.

Construir esse esqueleto do zero em JavaScript tradicional envolve roteamento, CSS de
layout, gerenciamento de estado e sincronização entre a barra lateral e a barra inferior.
No tempestweb, você descreve tudo isso em Python tipado — o framework cuida do resto.

Neste tutorial você vai aprender a:

- Montar o layout clássico de dashboard com `Scaffold`, `AppBar`, `Sidebar` e `NavBar`;
- Alternar seções usando apenas um `int` no estado (`active_tab`);
- Exibir KPIs em grade com `Grid` + `Card` + `Badge`;
- Criar alertas descartáveis com `Banner` e `Button`;
- Controlar a visibilidade da sidebar diretamente de uma seção de Settings;
- Compor usuários em tabela com `Avatar`, `Badge` e `Divider`.

!!! note "Nota"
    Este exemplo roda **sem nenhuma alteração** nos dois modos — WASM (Pyodide no
    browser) e Servidor (FastAPI + WebSocket). A mesma função `view()` Python serve
    os dois transportes.

---

## Pré-requisitos

Você já deve ter lido o [tutorial central](../tutorial/index.md) e saber o que são
`App`, `make_state` e `view`. Instale o tempestweb se ainda não o fez:

```bash
pip install tempestweb
tempestweb --version
```

---

## Estrutura do projeto

```
examples/
└── dashboard-shell/
    └── app.py
```

```bash
mkdir -p examples/dashboard-shell
touch examples/dashboard-shell/app.py
```

---

## Passo 1 — Imports e modelo de dados

Todo o código vive em um único arquivo. Começamos com os imports e com os dois
dataclasses que definem o estado da aplicação.

```python
"""Dashboard shell — demonstrates Scaffold + AppBar + Sidebar + NavBar layout.

Selecting a :class:`NavBar` item swaps the body content via state. The sidebar
shows navigation shortcuts identical to the bottom bar so the layout works at
any screen width. Both modes run this exact ``view`` unchanged::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AppBar,
    Avatar,
    Badge,
    Banner,
    Card,
    Divider,
    Grid,
    NavBar,
    Scaffold,
    Sidebar,
)
from tempest_core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
)
from tempest_core.style import AlignItems, Color, Edge, FontWeight
from tempest_core.widgets import Button, Column, Container, Row, Text

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_NAV_LABELS: list[str] = ["Overview", "Analytics", "Users", "Settings"]

_STAT_LABELS: list[str] = ["Revenue", "Sessions", "Signups", "Errors"]
_STAT_VALUES: list[str] = ["$128 400", "42 310", "1 870", "23"]
_STAT_TONES: list[str] = ["success", "info", "success", "error"]


@dataclass
class Alert:
    """A single dashboard alert entry.

    Attributes:
        message: The alert text.
        tone: The severity tone (info / success / warning / error).
        dismissed: Whether the user has dismissed this alert.
    """

    message: str
    tone: str
    dismissed: bool = False


@dataclass
class DashState:
    """Application state for the dashboard shell.

    Attributes:
        active_tab: Index of the currently selected navigation item.
        alerts: The list of active alerts shown on the Overview page.
        sidebar_open: Whether the collapsible sidebar is expanded.
    """

    active_tab: int = 0
    alerts: list[Alert] = field(
        default_factory=lambda: [
            Alert("Deploy #42 succeeded in production.", "success"),
            Alert("Queue depth above threshold — 1 200 jobs pending.", "warning"),
            Alert("Scheduled maintenance window in 3 hours.", "info"),
        ]
    )
    sidebar_open: bool = True


def make_state() -> DashState:
    """Build the initial dashboard state.

    Returns:
        A fresh :class:`DashState` landing on the Overview tab.
    """
    return DashState()
```

!!! tip "Dica — tokens de cor"
    `ACCENT`, `BACKGROUND`, `SURFACE`, `MUTED`, `ON_SURFACE` e `ON_MUTED` são
    constantes de cor semânticas definidas em `tempest_core.components.base`.
    Elas seguem o esquema de cores do tema padrão e facilitam a criação de UIs
    consistentes sem hardcodar valores hexadecimais.

**O que acabou de acontecer:**

- `_NAV_LABELS` lista as quatro seções — esse mesmo valor será reutilizado tanto na
  `Sidebar` quanto na `NavBar`, garantindo consistência.
- `Alert.dismissed` começa em `False`; quando o usuário clica em "✕", o estado
  muda para `True` e o alerta desaparece na próxima renderização.
- `DashState.sidebar_open` controla visibilidade da barra lateral — tanto pelo botão
  "☰" na `AppBar` quanto pelo botão na seção Settings.

---

## Passo 2 — Seção Overview: KPIs e alertas descartáveis

A seção Overview tem dois blocos: uma grade de KPIs e uma lista de alertas. Vamos
construir um componente auxiliar para cada cartão de métrica e depois montar o corpo.

```python
def _stat_card(label: str, value: str, tone: str) -> Widget:
    """Render a single KPI card.

    Args:
        label: The metric label shown above the value.
        value: The formatted metric value.
        tone: A tone string accepted by :class:`Badge` (``"success"`` /
            ``"error"`` / ``"info"``).

    Returns:
        A :class:`Card` with the label, value and a status badge.
    """
    return Card(
        key=f"stat-{label}",
        children=[
            Text(
                content=label,
                style=Style(font_size=13.0, color=ON_MUTED),
                key=f"stat-label-{label}",
            ),
            Text(
                content=value,
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key=f"stat-value-{label}",
            ),
            Badge(label=tone.upper(), tone=tone, key=f"stat-badge-{label}"),
        ],
    )


def _overview_body(app: App[DashState]) -> Widget:
    """Render the Overview section body.

    Shows a KPI stats grid and the dismissible alert list.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` with the stats grid and alert banners.
    """

    def dismiss(index: int) -> None:
        """Dismiss the alert at *index*."""

        def mutate(s: DashState) -> None:
            s.alerts[index].dismissed = True

        app.set_state(mutate)

    stats_grid = Grid(
        key="stats-grid",
        columns=2,
        gap=12.0,
        children=[
            _stat_card(lbl, val, tone)
            for lbl, val, tone in zip(
                _STAT_LABELS, _STAT_VALUES, _STAT_TONES, strict=False
            )
        ],
    )

    visible_alerts: list[Widget] = []
    for idx, alert in enumerate(app.state.alerts):
        if alert.dismissed:
            continue
        i = idx  # capture loop variable

        def _make_dismiss(bound_i: int) -> Widget:
            return Button(
                label="✕",
                on_click=lambda _i=bound_i: dismiss(_i),
                key=f"dismiss-{bound_i}",
                style=Style(
                    padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
                    radius=6.0,
                    background=Color.from_hex("#ffffff22"),
                    color=ON_SURFACE,
                    font_size=12.0,
                ),
            )

        visible_alerts.append(
            Banner(
                message=alert.message,
                tone=alert.tone,
                action=_make_dismiss(i),
                key=f"alert-{i}",
            )
        )

    alerts_section: Widget = Column(
        key="alerts-col",
        style=Style(gap=8.0),
        children=visible_alerts
        if visible_alerts
        else [
            Text(
                content="No active alerts.",
                style=Style(color=ON_MUTED, font_size=14.0),
                key="no-alerts",
            )
        ],
    )

    return Column(
        key="overview-body",
        style=Style(gap=20.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Key Metrics",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="metrics-heading",
            ),
            stats_grid,
            Text(
                content="Alerts",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="alerts-heading",
            ),
            alerts_section,
        ],
    )
```

!!! info "Info — `Grid` vs `Row`"
    `Grid(columns=2, gap=12.0)` distribui os filhos em duas colunas de largura igual,
    com espaçamento de 12 px. Use `Grid` quando o número de itens for par e você quiser
    colunas simétricas; use `Row` quando precisar controlar `grow` individualmente.

!!! warning "Aviso — captura de variável de loop"
    No Python, closures capturam a *variável*, não o *valor*. Por isso o loop usa
    `i = idx` e a função auxiliar `_make_dismiss(bound_i)` recebe o índice como
    argumento. Sem isso, todos os botões fechariam sempre o último alerta.

**Destaques:**

| Widget | Para que serve aqui |
|---|---|
| `Grid(columns=2)` | Grade de KPIs em duas colunas |
| `Badge(tone="success")` | Indicador colorido de status — verde, vermelho ou azul |
| `Banner(message=..., tone=..., action=...)` | Faixa de alerta com botão de ação à direita |
| `Button(label="✕", on_click=...)` | Botão de descarte do alerta |

---

## Passo 3 — Seção Analytics: tabela de tráfego

A seção Analytics renderiza um `Card` contendo linhas de período + sessões + variação,
separadas por `Divider`.

```python
def _analytics_body() -> Widget:
    """Render the Analytics section placeholder.

    Returns:
        A :class:`Column` describing the Analytics page content.
    """
    rows: list[Widget] = []
    periods: list[tuple[str, str, str]] = [
        ("This week", "8 340", "+12 %"),
        ("Last week", "7 450", "+5 %"),
        ("This month", "32 100", "+9 %"),
        ("Last month", "29 500", "+3 %"),
    ]
    for period, sessions, change in periods:
        rows.append(
            Row(
                key=f"row-{period}",
                style=Style(
                    gap=12.0,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(vertical=10.0, horizontal=4.0),
                ),
                children=[
                    Text(
                        content=period,
                        style=Style(grow=1.0, color=ON_SURFACE, font_size=14.0),
                        key=f"period-{period}",
                    ),
                    Text(
                        content=sessions,
                        style=Style(
                            color=ON_SURFACE,
                            font_size=14.0,
                            font_weight=FontWeight.BOLD,
                        ),
                        key=f"sessions-{period}",
                    ),
                    Text(
                        content=change,
                        style=Style(
                            color=Color.from_hex("#16a34a"),
                            font_size=13.0,
                        ),
                        key=f"change-{period}",
                    ),
                ],
            )
        )
        rows.append(Divider(key=f"div-{period}"))

    return Column(
        key="analytics-body",
        style=Style(gap=16.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Traffic by Period",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="analytics-heading",
            ),
            Card(key="analytics-card", children=rows),
        ],
    )
```

!!! tip "Dica — `Style(grow=1.0)`"
    `grow=1.0` no `Text` de período faz aquela célula ocupar todo o espaço
    disponível na linha, empurrando os valores de sessões e variação para a direita —
    o equivalente a `flex: 1` no CSS.

---

## Passo 4 — Seção Users: tabela com avatares e badges de papel

```python
def _users_body() -> Widget:
    """Render the Users section with a sample user table.

    Returns:
        A :class:`Column` showing a list of sample users.
    """
    users: list[tuple[str, str, str]] = [
        ("Alice Martin", "alice@example.com", "Admin"),
        ("Bob Chen", "bob@example.com", "Editor"),
        ("Clara Neves", "clara@example.com", "Viewer"),
        ("David Park", "david@example.com", "Editor"),
        ("Eva Rossi", "eva@example.com", "Viewer"),
    ]

    header = Row(
        key="users-header",
        style=Style(
            gap=8.0,
            padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
            background=MUTED,
        ),
        children=[
            Text(
                content="Name",
                style=Style(
                    grow=2.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-name",
            ),
            Text(
                content="Email",
                style=Style(
                    grow=3.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-email",
            ),
            Text(
                content="Role",
                style=Style(
                    grow=1.0,
                    font_size=13.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_MUTED,
                ),
                key="h-role",
            ),
        ],
    )

    user_rows: list[Widget] = [header]
    for name, email, role in users:
        user_rows.append(
            Row(
                key=f"user-{name}",
                style=Style(
                    gap=8.0,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                ),
                children=[
                    Text(
                        content=name,
                        style=Style(grow=2.0, font_size=14.0, color=ON_SURFACE),
                        key=f"name-{name}",
                    ),
                    Text(
                        content=email,
                        style=Style(grow=3.0, font_size=14.0, color=ON_MUTED),
                        key=f"email-{name}",
                    ),
                    Badge(label=role, tone="info", key=f"role-{name}"),
                ],
            )
        )
        user_rows.append(Divider(key=f"udiv-{name}"))

    return Column(
        key="users-body",
        style=Style(gap=16.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="Team Members",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="users-heading",
            ),
            Card(key="users-card", children=user_rows),
        ],
    )
```

!!! info "Info — proporções de coluna com `grow`"
    O cabeçalho e cada linha de usuário usam `grow=2.0` para o nome, `grow=3.0` para
    o e-mail e `grow=1.0` para o papel. Isso garante que as colunas se alinhem
    consistentemente sem precisar de larguras fixas.

---

## Passo 5 — Seção Settings: toggle interativo da sidebar

A seção Settings demonstra algo especial: ela altera a **estrutura do layout** ao
abrir/fechar a barra lateral — usando o mesmo `set_state` que troca de aba.

```python
def _settings_body(app: App[DashState]) -> Widget:
    """Render the Settings section.

    Includes a sidebar-toggle control so the layout itself is interactive.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` with the settings controls.
    """

    def toggle_sidebar() -> None:
        """Toggle the sidebar open/closed."""
        app.set_state(lambda s: setattr(s, "sidebar_open", not s.sidebar_open))

    sidebar_label = "Hide Sidebar" if app.state.sidebar_open else "Show Sidebar"

    return Column(
        key="settings-body",
        style=Style(gap=20.0, padding=Edge.all(20.0), background=BACKGROUND),
        children=[
            Text(
                content="App Settings",
                style=Style(
                    font_size=16.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="settings-heading",
            ),
            Card(
                key="settings-card",
                children=[
                    Text(
                        content="Layout",
                        style=Style(
                            font_size=14.0,
                            font_weight=FontWeight.BOLD,
                            color=ON_SURFACE,
                        ),
                        key="layout-label",
                    ),
                    Divider(key="settings-div"),
                    Row(
                        key="sidebar-toggle-row",
                        style=Style(
                            gap=12.0,
                            align=AlignItems.CENTER,
                            padding=Edge.symmetric(vertical=8.0, horizontal=0.0),
                        ),
                        children=[
                            Text(
                                content="Sidebar",
                                style=Style(grow=1.0, color=ON_SURFACE, font_size=14.0),
                                key="sidebar-label-text",
                            ),
                            Button(
                                label=sidebar_label,
                                on_click=toggle_sidebar,
                                key="sidebar-toggle-btn",
                                style=Style(
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=16.0
                                    ),
                                    radius=8.0,
                                    background=ACCENT,
                                    color=ON_SURFACE,
                                    font_size=14.0,
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

!!! tip "Dica — rótulo dinâmico"
    `sidebar_label` é calculado *antes* de montar a árvore de widgets: `"Hide Sidebar"`
    se a sidebar está aberta, `"Show Sidebar"` se está fechada. O botão então exibe
    sempre o texto correto para o estado atual, sem lógica condicional dentro do widget.

---

## Passo 6 — Navegação na sidebar

A sidebar tem sua própria lista de botões de navegação, sincronizada com `active_tab`.
O botão ativo recebe destaque visual via `background=ACCENT`.

```python
def _sidebar_nav(app: App[DashState]) -> Widget:
    """Build the sidebar navigation links.

    Each link button changes the active tab; the active one is highlighted.

    Args:
        app: The application handle.

    Returns:
        A :class:`Column` of navigation buttons plus a user footer.
    """

    def make_nav_handler(index: int) -> Callable[[], None]:
        """Create a tab-selection handler for *index*.

        Args:
            index: The tab index to activate.

        Returns:
            A zero-argument callable that sets the active tab.
        """

        def handler() -> None:
            app.set_state(lambda s: setattr(s, "active_tab", index))

        return handler

    nav_buttons: list[Widget] = []
    for idx, label in enumerate(_NAV_LABELS):
        active = idx == app.state.active_tab
        nav_buttons.append(
            Button(
                label=label,
                on_click=make_nav_handler(idx),
                key=f"sidenav-{idx}",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                    radius=8.0,
                    background=ACCENT if active else Color.from_hex("#00000000"),
                    color=ON_SURFACE if active else ON_MUTED,
                    font_size=14.0,
                    font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
                ),
            )
        )

    return Column(
        key="sidebar-nav-col",
        style=Style(gap=4.0, background=SURFACE),
        children=[
            Container(
                key="brand",
                style=Style(
                    padding=Edge.symmetric(vertical=16.0, horizontal=12.0),
                ),
                child=Text(
                    content="◈ Dashboard",
                    style=Style(
                        font_size=18.0,
                        font_weight=FontWeight.BOLD,
                        color=ON_SURFACE,
                    ),
                    key="brand-text",
                ),
            ),
            Divider(key="brand-div"),
            *nav_buttons,
            Container(
                key="sidebar-spacer",
                style=Style(grow=1.0),
            ),
            Divider(key="user-div"),
            Row(
                key="user-row",
                style=Style(
                    gap=10.0,
                    align=AlignItems.CENTER,
                    padding=Edge.all(12.0),
                ),
                children=[
                    Avatar(initials="MB", size=36.0, key="user-avatar"),
                    Column(
                        key="user-info",
                        style=Style(gap=2.0),
                        children=[
                            Text(
                                content="Mauricio B.",
                                style=Style(
                                    font_size=13.0,
                                    font_weight=FontWeight.BOLD,
                                    color=ON_SURFACE,
                                ),
                                key="user-name",
                            ),
                            Text(
                                content="Admin",
                                style=Style(font_size=11.0, color=ON_MUTED),
                                key="user-role",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

!!! info "Info — `Container` como espaçador"
    `Container(style=Style(grow=1.0))` sem filhos empurra o rodapé do usuário para o
    fundo da sidebar — o equivalente a `margin-top: auto` no CSS flexbox.

**Destaques da sidebar:**

- `make_nav_handler(index)` usa o padrão factory para capturar corretamente o índice
  em cada iteração do loop.
- `Color.from_hex("#00000000")` é transparente — o botão inativo não exibe fundo.
- O rodapé exibe `Avatar` + nome + papel do usuário logado.

---

## Passo 7 — A função `view`: montando tudo

Com todas as peças prontas, a função `view` monta o layout completo.

```python
def _body_for_tab(tab: int, app: App[DashState]) -> Widget:
    """Return the body widget matching the active tab index.

    Args:
        tab: The currently selected tab index.
        app: The application handle passed to tab bodies that need state.

    Returns:
        The section body widget for ``tab``.
    """
    if tab == 0:
        return _overview_body(app)
    if tab == 1:
        return _analytics_body()
    if tab == 2:
        return _users_body()
    return _settings_body(app)


def view(app: App[DashState]) -> Widget:
    """Render the full dashboard shell from the current state.

    The layout is: AppBar on top, then a ``Row`` containing an optional
    ``Sidebar`` on the left and the active section body filling the rest.
    A ``NavBar`` at the bottom mirrors the sidebar for compact viewports.
    Selecting a nav item in either bar updates ``active_tab`` via
    ``app.set_state``, which triggers a re-render swapping the body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_nav_select(index: int) -> None:
        """Handle bottom NavBar item selection.

        Args:
            index: The selected item index.
        """
        app.set_state(lambda s: setattr(s, "active_tab", index))

    appbar = AppBar(
        key="main-appbar",
        title=f"Dashboard — {_NAV_LABELS[app.state.active_tab]}",
        leading=Button(
            label="☰",
            on_click=lambda: app.set_state(
                lambda s: setattr(s, "sidebar_open", not s.sidebar_open)
            ),
            key="menu-btn",
            style=Style(
                padding=Edge.all(8.0),
                radius=6.0,
                background=MUTED,
                color=ON_SURFACE,
                font_size=16.0,
            ),
        ),
        actions=[
            Avatar(initials="MB", size=32.0, key="appbar-avatar"),
        ],
    )

    sidebar = Sidebar(
        key="main-sidebar",
        width=220.0,
        children=[_sidebar_nav(app)],
    )

    section_body = _body_for_tab(app.state.active_tab, app)

    main_row_children: list[Widget] = []
    if app.state.sidebar_open:
        main_row_children.append(sidebar)
    main_row_children.append(
        Container(
            key="content-area",
            style=Style(grow=1.0, background=BACKGROUND),
            child=section_body,
        )
    )

    main_row = Row(
        key="main-row",
        style=Style(grow=1.0, align=AlignItems.START),
        children=main_row_children,
    )

    bottom_nav = NavBar(
        key="bottom-nav",
        items=_NAV_LABELS,
        active=app.state.active_tab,
        on_select=on_nav_select,
    )

    return Scaffold(
        key="dashboard-scaffold",
        app_bar=appbar,
        body=main_row,
        bottom_bar=bottom_nav,
    )
```

**O que está acontecendo na `view`:**

| Peça | Responsabilidade |
|---|---|
| `AppBar(title=..., leading=..., actions=[...])` | Barra superior com título dinâmico, botão de menu e avatar |
| `Sidebar(width=220.0, children=[...])` | Painel lateral de 220 px com navegação |
| `if app.state.sidebar_open` | Inclui ou omite a sidebar na lista de filhos do `Row` |
| `Container(style=Style(grow=1.0))` | Área de conteúdo que expande para preencher o espaço restante |
| `NavBar(items=..., active=..., on_select=...)` | Barra inferior que espelha a navegação da sidebar |
| `Scaffold(app_bar=..., body=..., bottom_bar=...)` | Estrutura raiz que posiciona AppBar, corpo e barra inferior |

!!! warning "Aviso — sincronização sidebar ↔ NavBar"
    Tanto a `Sidebar` quanto a `NavBar` chamam `set_state(lambda s: setattr(s, "active_tab", index))`.
    Como o estado é a única fonte de verdade, ambas ficam automaticamente sincronizadas.
    Nunca duplique o estado ativo — um único `int` governa todo o layout.

---

## Passo 8 — Executar o app

Execute no **Modo A** (Python no browser via Pyodide/WASM):

```bash
tempestweb dev --mode wasm --path examples/dashboard-shell
```

Execute no **Modo B** (Python no servidor via FastAPI + WebSocket):

```bash
tempestweb dev --mode server --path examples/dashboard-shell
```

Abra `http://localhost:8000` no browser. Você deve ver:

- ✅ `AppBar` com título "Dashboard — Overview" e botão "☰" à esquerda;
- ✅ `Sidebar` de 220 px com quatro links de navegação e rodapé de usuário;
- ✅ Grade 2×2 com os quatro KPIs (Revenue, Sessions, Signups, Errors);
- ✅ Três alertas descartáveis — clicar em "✕" remove cada um individualmente;
- ✅ Clicar em "Analytics" na sidebar ou na barra inferior troca o corpo;
- ✅ A seção "Settings" permite esconder/mostrar a sidebar em tempo real;
- ✅ O título da `AppBar` atualiza para refletir a seção ativa.

---

## Recapitulando

Neste tutorial você construiu um shell de dashboard completo e aprendeu:

- 💡 **`Scaffold`** é o widget raiz que organiza `app_bar`, `body` e `bottom_bar`
  em um layout de tela padrão.
- 💡 **`Sidebar` + `NavBar`** são dois pontos de entrada para a mesma navegação —
  ambos escrevem em `active_tab` e ficam sincronizados automaticamente.
- 💡 **`Grid(columns=2)`** distribui KPIs em duas colunas de forma equilibrada.
- 💡 **`Banner(tone=..., action=...)`** cria alertas descartáveis com um widget de
  ação integrado — basta passar um `Button` como `action`.
- 💡 **`Badge(tone=...)`** é o bloco visual mais simples para indicar status ou papel.
- 💡 A **visibilidade da sidebar** é apenas um `bool` no estado — incluir ou omitir
  o widget na lista de filhos do `Row` é o suficiente para mostrar ou ocultar.
- 💡 O mesmo `app.py` roda sem alteração nos dois modos — WASM e Servidor.

---

## Próximos passos

- Leia o [tutorial central](../tutorial/index.md) para entender o ciclo de vida
  completo do tempestweb.
- Explore abas com `TabView` no exemplo [Perfil com Abas](tabs-profile.md).
- Veja como construir tabelas de dados com filtro e paginação no exemplo
  [Data Table](data-table.md).
