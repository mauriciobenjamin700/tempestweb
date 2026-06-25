# Core app shell — layout e navegação 🚀

Neste exemplo você vai montar o **esqueleto clássico de uma aplicação**: uma barra
de topo (`AppBar`), uma navegação lateral (`Sidebar` + `NavBar` + `ListTile`) e
uma região de conteúdo (`Card`) que troca conforme o item selecionado. Tudo é um
`Scaffold` controlado por estado Python tipado.

---

## O que você vai construir

- 🧱 Um **Scaffold** com `AppBar` no topo.
- 🧭 Uma **Sidebar** com `NavBar` (seleção) e `ListTile` (descritores ricos).
- 🗂️ Um **Card** de conteúdo que troca de heading/body ao navegar.

---

## Pré-requisitos

```bash
pip install tempestweb
```

!!! tip "Dica"
    Se você ainda não conhece o ciclo estado → view → patches, leia o
    [tutorial de introdução](../tutorial/index.md).

---

## Passo 1 — O destino de navegação

Cada destino é um `NavItem` imutável que carrega tudo o que aparece na barra
lateral **e** no conteúdo.

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NavItem:
    """A single navigation destination in the app shell.

    Attributes:
        label: The short label shown in the navigation bar.
        subtitle: A one-line description rendered beside the label.
        heading: The page heading shown in the content region.
        body: The page body text shown in the content region.
    """

    label: str
    subtitle: str
    heading: str
    body: str


NAV_ITEMS: list[NavItem] = [
    NavItem(
        label="Home",
        subtitle="Overview and quick stats",
        heading="Welcome home",
        body="This is the home page of the app shell. Pick a destination "
        "on the left to swap the content region.",
    ),
    NavItem(
        label="Reports",
        subtitle="Charts and exports",
        heading="Reports",
        body="The reports page would render charts and downloadable exports. "
        "Here it is a placeholder driven entirely by state.",
    ),
    NavItem(
        label="Settings",
        subtitle="Preferences and account",
        heading="Settings",
        body="The settings page would expose preferences and account "
        "controls. The shell layout stays identical across pages.",
    ),
]
```

---

## Passo 2 — O estado

O estado guarda só o índice do destino ativo.

```python
@dataclass
class ShellState:
    """State for the app-shell example.

    Attributes:
        selected: Index into :data:`NAV_ITEMS` of the active destination.
        items: The available navigation destinations.
    """

    selected: int = 0
    items: list[NavItem] = field(default_factory=lambda: list(NAV_ITEMS))


def make_state() -> ShellState:
    """Build the initial state.

    Returns:
        A fresh :class:`ShellState` with the first destination selected.
    """
    return ShellState()
```

---

## Passo 3 — A barra lateral

A `Sidebar` agrupa um `NavBar` (que possui a seleção via `on_select`) e uma lista
de `ListTile` (descritores mais ricos). O tile ativo recebe `color_scheme="primary"`.

```python
from tempest_core import App, Text, Widget
from tempestweb.components import ListTile, NavBar, Sidebar

def _build_sidebar(app: App[ShellState]) -> Sidebar:
    """Build the side navigation for the shell."""
    state: ShellState = app.state

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "selected", index))

    tiles: list[Widget] = [
        ListTile(
            key=f"tile-{i}",
            title=item.label,
            subtitle=item.subtitle,
            color_scheme="primary" if i == state.selected else None,
        )
        for i, item in enumerate(state.items)
    ]

    return Sidebar(
        key="sidebar",
        width=260.0,
        children=[
            Text(content="Navigation", key="nav-title"),
            NavBar(
                key="navbar",
                items=[item.label for item in state.items],
                active=state.selected,
                on_select=select,
            ),
            *tiles,
        ],
    )
```

!!! info "Info — `NavBar.on_select` recebe o índice"
    O `NavBar` chama `on_select(index)` com o índice do item clicado. Guardamos
    esse índice em `state.selected` e tudo o mais é derivado a partir dele.

---

## Passo 4 — A região de conteúdo

O `Card` de conteúdo simplesmente lê o `NavItem` ativo e renderiza seu heading e
body.

```python
from tempest_core import Text
from tempestweb.components import Card

def _build_content(app: App[ShellState]) -> Card:
    """Build the content region for the active destination."""
    state: ShellState = app.state
    active: NavItem = state.items[state.selected]

    return Card(
        key="content",
        children=[
            Text(content=active.heading, key="content-heading"),
            Text(content=active.body, key="content-body"),
        ],
    )
```

---

## Passo 5 — O Scaffold

O `Scaffold` une tudo: `app_bar` no topo e `body` com a barra lateral + conteúdo.

```python
from tempest_core import Column, Style
from tempest_core.style import Edge
from tempestweb.components import AppBar, Scaffold

return Scaffold(
    key="shell",
    app_bar=AppBar(title="Core App Shell", key="appbar"),
    body=Column(
        key="shell-body",
        style=Style(gap=16.0, padding=Edge.all(16)),
        children=[
            _build_sidebar(app),
            _build_content(app),
        ],
    ),
)
```

---

## O app completo

```python
"""Core App Shell — a layout/navigation scaffolding showcase.

This example demonstrates the core's structural components working together to
form a classic application shell: a top bar, a side navigation, and a content
region that swaps based on the selected navigation item.

Like every tempestweb example, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import AppBar, Card, ListTile, NavBar, Scaffold, Sidebar


@dataclass(frozen=True)
class NavItem:
    """A single navigation destination in the app shell.

    Attributes:
        label: The short label shown in the navigation bar.
        subtitle: A one-line description rendered beside the label.
        heading: The page heading shown in the content region.
        body: The page body text shown in the content region.
    """

    label: str
    subtitle: str
    heading: str
    body: str


NAV_ITEMS: list[NavItem] = [
    NavItem(
        label="Home",
        subtitle="Overview and quick stats",
        heading="Welcome home",
        body="This is the home page of the app shell. Pick a destination "
        "on the left to swap the content region.",
    ),
    NavItem(
        label="Reports",
        subtitle="Charts and exports",
        heading="Reports",
        body="The reports page would render charts and downloadable exports. "
        "Here it is a placeholder driven entirely by state.",
    ),
    NavItem(
        label="Settings",
        subtitle="Preferences and account",
        heading="Settings",
        body="The settings page would expose preferences and account "
        "controls. The shell layout stays identical across pages.",
    ),
]


@dataclass
class ShellState:
    """State for the app-shell example.

    Attributes:
        selected: Index into :data:`NAV_ITEMS` of the active destination.
        items: The available navigation destinations.
    """

    selected: int = 0
    items: list[NavItem] = field(default_factory=lambda: list(NAV_ITEMS))


def make_state() -> ShellState:
    """Build the initial state.

    Returns:
        A fresh :class:`ShellState` with the first destination selected.
    """
    return ShellState()


def _build_sidebar(app: App[ShellState]) -> Sidebar:
    """Build the side navigation for the shell.

    The :class:`NavBar` owns selection (via ``on_select``) while the
    :class:`ListTile` rows give each destination a richer descriptor.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The configured :class:`Sidebar` widget.
    """
    state: ShellState = app.state

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "selected", index))

    tiles: list[Widget] = [
        ListTile(
            key=f"tile-{i}",
            title=item.label,
            subtitle=item.subtitle,
            color_scheme="primary" if i == state.selected else None,
        )
        for i, item in enumerate(state.items)
    ]

    return Sidebar(
        key="sidebar",
        width=260.0,
        children=[
            Text(content="Navigation", key="nav-title"),
            NavBar(
                key="navbar",
                items=[item.label for item in state.items],
                active=state.selected,
                on_select=select,
            ),
            *tiles,
        ],
    )


def _build_content(app: App[ShellState]) -> Card:
    """Build the content region for the active destination.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Card` rendering the selected page's heading and body.
    """
    state: ShellState = app.state
    active: NavItem = state.items[state.selected]

    return Card(
        key="content",
        children=[
            Text(content=active.heading, key="content-heading"),
            Text(content=active.body, key="content-body"),
        ],
    )


def view(app: App[ShellState]) -> Widget:
    """Render the app shell from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    return Scaffold(
        key="shell",
        app_bar=AppBar(title="Core App Shell", key="appbar"),
        body=Column(
            key="shell-body",
            style=Style(gap=16.0, padding=Edge.all(16)),
            children=[
                _build_sidebar(app),
                _build_content(app),
            ],
        ),
    )
```

---

## Rodando o exemplo ▶

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm examples/core-app-shell/app.py
    ```

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/core-app-shell/app.py
    ```

!!! check "Verificação"
    Você deve ver a barra de topo "Core App Shell", uma barra lateral com Home /
    Reports / Settings, e um cartão de conteúdo. Clique em **Reports** → o tile
    fica destacado e o cartão troca o heading e o body. ✅

---

## Recapitulando

- ✅ Montar um shell de app com `Scaffold` (`app_bar` + `body`).
- ✅ Compor navegação com `Sidebar` + `NavBar` (`on_select`) + `ListTile`.
- ✅ Trocar o conteúdo derivando o `NavItem` ativo de um único índice no estado.
- ✅ Destacar o item ativo com `color_scheme="primary"`.
- ✅ Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Próximos passos"
    - Veja o [Dashboard app shell](dashboard-shell.md) para um layout mais completo.
    - Combine com [Drawer de navegação e rotas](router-drawer.md) para rotas reais.
