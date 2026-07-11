# Drawer de Navegação e Rotas 🗂️

> Construa um site de documentação com painel lateral deslizante, navegação em
> dois níveis via `app.push` / `app.pop` / `app.reset` e uma trilha de
> breadcrumb clicável.

---

## O que vamos construir

Neste tutorial você vai criar um mini-site de documentação totalmente navegável
em Python puro.  Ele terá:

- Um **`RouteDrawer`** — o painel lateral que desliza sobre o conteúdo.
- Uma **pilha de rotas** com `app.push`, `app.pop` e `app.reset` para navegar
  entre seções e artigos.
- Um **`Breadcrumb`** clicável que mostra onde o usuário está e permite voltar a
  qualquer ponto da trilha.
- Um **`AppBar`** dinâmico que troca o ícone de hambúrguer por uma seta "←"
  quando há páginas para voltar.

!!! note "Pré-requisitos"
    - Leia primeiro [Primeiros Passos](../tutorial/index.md) para entender o
      ciclo `make_state → view → rebuild`.
    - Se quiser entender como os patches chegam ao DOM, leia
      [Como os Patches Funcionam](../tutorial/patches.md).

---

## 1. Instale e crie os arquivos

```bash
pip install tempestweb
mkdir -p examples/router-drawer
touch examples/router-drawer/app.py
```

---

## 2. O catálogo de conteúdo

A navegação precisa de dados.  Vamos declarar três dicionários estáticos que
descrevem as seções, os artigos de cada seção e os textos de cada página.

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import App, NavStack, Route, Style, Widget, build
from tempest_core.components import (
    AppBar,
    Breadcrumb,
    Card,
    Divider,
    ListTile,
    Scaffold,
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
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    RouteDrawer,
    Row,
    Text,
)

# Seções disponíveis no drawer
_SECTIONS: list[tuple[str, str]] = [
    ("Getting Started", "/getting-started"),
    ("Core Concepts", "/core-concepts"),
    ("Widgets", "/widgets"),
    ("Deployment", "/deployment"),
]

# Artigos por seção
_ARTICLES: dict[str, list[tuple[str, str]]] = {
    "/getting-started": [
        ("Installation", "/getting-started/installation"),
        ("Quick Start", "/getting-started/quickstart"),
        ("Project Layout", "/getting-started/layout"),
    ],
    "/core-concepts": [
        ("Widget Tree", "/core-concepts/widget-tree"),
        ("State & Rebuild", "/core-concepts/state"),
        ("Navigation Stack", "/core-concepts/navigation"),
    ],
    "/widgets": [
        ("Layout Widgets", "/widgets/layout"),
        ("Input Widgets", "/widgets/inputs"),
        ("Navigation Widgets", "/widgets/navigation"),
    ],
    "/deployment": [
        ("Mode A — WASM", "/deployment/wasm"),
        ("Mode B — Server", "/deployment/server"),
        ("Docker", "/deployment/docker"),
    ],
}

# Texto de cada página
_CONTENT: dict[str, str] = {
    "/getting-started": (
        "Welcome! This guide walks you through setting up tempestweb, "
        "writing your first app, and understanding the project layout."
    ),
    "/getting-started/installation": (
        "Install tempestweb with pip:\n\n"
        "    pip install tempestweb\n\n"
        "Python 3.11+ is required. Both WASM and server runtimes are included."
    ),
    "/getting-started/quickstart": (
        "Create app.py, define make_state() and view(), then run:\n\n"
        "    tempestweb dev --mode wasm"
    ),
    "/getting-started/layout": (
        "The canonical layout is a single app.py per example.\n"
        "Larger apps can split into multiple modules imported by app.py."
    ),
    "/core-concepts": (
        "Learn about the widget tree, state management and the navigation stack."
    ),
    "/core-concepts/widget-tree": (
        "The widget tree is a declarative, typed Pydantic model graph.\n"
        "The reconciler diffs two trees and emits minimal patches."
    ),
    "/core-concepts/state": (
        "State lives in a plain Python dataclass.\n"
        "Call app.set_state(lambda s: ...) to mutate it and schedule a rebuild."
    ),
    "/core-concepts/navigation": (
        "The NavStack is a list of Route objects.\n"
        "app.push(), app.pop() and app.replace() mutate it and schedule a rebuild."
    ),
    "/widgets": "Browse the full widget catalogue organised by category.",
    "/widgets/layout": (
        "Column, Row, Container, Stack, Wrap, ScrollView and Grid "
        "cover the full flex layout surface."
    ),
    "/widgets/inputs": (
        "Input, TextArea, Checkbox, Switch, Slider, Dropdown, DatePicker and "
        "more — all typed, all async-first."
    ),
    "/widgets/navigation": (
        "Navigator, RouteDrawer, TabView, TabBar — navigation host widgets "
        "that keep state in the declarative tree."
    ),
    "/deployment": "Choose between Mode A (WASM) and Mode B (server + WebSocket).",
    "/deployment/wasm": (
        "Mode A runs Python in the browser via Pyodide.\n"
        "No server needed — the entire app ships as static files."
    ),
    "/deployment/server": (
        "Mode B runs Python on the server and pushes patches over WebSocket.\n"
        "Great for I/O-heavy apps that need server-side resources."
    ),
    "/deployment/docker": (
        "A single Dockerfile covers Mode B.\n"
        "Set TEMPESTWEB_MODE=server and expose port 8000."
    ),
}
```

!!! tip "Dica — dados estáticos são Python puro"
    Perceba que `_SECTIONS`, `_ARTICLES` e `_CONTENT` são dicionários e listas
    normais.  O tempestweb não exige nenhum formato especial de dados — qualquer
    estrutura Python funciona dentro de `view()`.

---

## 3. O estado

Todo o estado do app cabe em dois campos:

```python
@dataclass
class DrawerNavState:
    """Application state for the drawer-navigation demo.

    Attributes:
        drawer_open: Whether the navigation drawer is currently expanded.
        history_labels: Human-readable crumb labels for the breadcrumb trail,
            parallel to ``app.nav.stack``.
    """

    drawer_open: bool = False
    history_labels: list[str] = field(default_factory=lambda: ["Home"])


def make_state() -> DrawerNavState:
    """Build the initial drawer-navigation state.

    Returns:
        A fresh DrawerNavState with the drawer closed and the
        breadcrumb trail showing only the root crumb.
    """
    return DrawerNavState()
```

- **`drawer_open`** — `True` enquanto o painel lateral estiver visível.
- **`history_labels`** — lista de rótulos legíveis que espelham a pilha de rotas
  (`app.nav.stack`).  Usamos rótulos separados porque a pilha guarda apenas
  nomes de rota (`"/getting-started"`), mas o breadcrumb precisa mostrar
  `"Getting Started"`.

!!! info "NavStack e State andam juntos"
    O tempestweb mantém duas pilhas: `app.nav.stack` (rotas) e
    `state.history_labels` (rótulos legíveis).  Cada `push` / `pop` / `reset`
    deve ser acompanhado de um `app.set_state` equivalente para mantê-las
    sincronizadas.

---

## 4. Funções auxiliares de conteúdo

Antes de montar o `view` completo, vamos criar três funções que renderizam o
conteúdo de acordo com a rota atual.

### 4.1 Página de artigo (folha)

```python
def _article_body(route_name: str) -> Widget:
    """Render the content body for a leaf article page.

    Args:
        route_name: The current route name, used to look up the article text.

    Returns:
        A Card containing the article content text.
    """
    content = _CONTENT.get(route_name, "Content coming soon.")
    return Column(
        key="article-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Card(
                key="article-card",
                children=[
                    Text(
                        content=content,
                        key="article-text",
                        style=Style(
                            font_size=15.0,
                            color=ON_SURFACE,
                        ),
                    ),
                ],
            ),
        ],
    )
```

### 4.2 Índice de seção

```python
def _section_body(
    route_name: str,
    app: App[DrawerNavState],
) -> Widget:
    """Render the index page for a top-level section showing its articles.

    Args:
        route_name: The section's route name (e.g. "/getting-started").
        app: The application handle for wiring navigation handlers.

    Returns:
        A Column of tappable article tiles plus an intro paragraph.
    """
    articles = _ARTICLES.get(route_name, [])

    def make_nav_handler(title: str, article_route: str) -> Callable[[], None]:
        """Build a handler that navigates to article_route."""

        def handler() -> None:
            """Navigate to the article and append its crumb."""
            app.push(Route(name=article_route))
            app.set_state(lambda s: s.history_labels.append(title))

        return handler

    tiles: list[Widget] = []
    for title, article_route in articles:
        tiles.append(
            ListTile(
                key=f"tile-{article_route}",
                title=title,
                subtitle="Tap to read",
                trailing=Button(
                    label="→",
                    on_click=make_nav_handler(title, article_route),
                    key=f"tile-btn-{article_route}",
                    style=Style(
                        padding=Edge.symmetric(vertical=6.0, horizontal=12.0),
                        radius=6.0,
                        background=ACCENT,
                        color=ON_SURFACE,
                        font_size=13.0,
                    ),
                ),
            )
        )
        tiles.append(Divider(key=f"div-{article_route}"))

    intro = _CONTENT.get(route_name, "")

    return Column(
        key="section-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Text(
                content=intro,
                key="section-intro",
                style=Style(font_size=15.0, color=ON_MUTED),
            ),
            Card(key="articles-card", children=tiles)
            if tiles
            else Container(key="no-tiles"),
        ],
    )
```

!!! tip "Dica — closure para handlers"
    A função interna `make_nav_handler` captura `title` e `article_route` no
    closure.  Esse padrão é essencial em loops: sem ele, todas as lambdas
    capturariam as variáveis do **último** item da lista, um bug clássico de
    Python.

### 4.3 Tela inicial

```python
def _home_body(app: App[DrawerNavState]) -> Widget:
    """Render the root home screen with section entry points.

    Args:
        app: The application handle for wiring navigation handlers.

    Returns:
        A Column with cards for each top-level section.
    """

    def make_section_handler(label: str, route: str) -> Callable[[], None]:
        """Build a handler that navigates to route."""

        def handler() -> None:
            """Navigate to the section and record its breadcrumb label."""
            app.push(Route(name=route))
            app.set_state(lambda s: s.history_labels.append(label))

        return handler

    section_cards: list[Widget] = []
    for label, route in _SECTIONS:
        section_cards.append(
            Card(
                key=f"section-card-{route}",
                children=[
                    Row(
                        key=f"section-row-{route}",
                        style=Style(
                            gap=12.0,
                            align=AlignItems.CENTER,
                        ),
                        children=[
                            Column(
                                key=f"section-info-{route}",
                                style=Style(gap=4.0, grow=1.0),
                                children=[
                                    Text(
                                        content=label,
                                        key=f"section-title-{route}",
                                        style=Style(
                                            font_size=16.0,
                                            font_weight=FontWeight.BOLD,
                                            color=ON_SURFACE,
                                        ),
                                    ),
                                    Text(
                                        content=(
                                            f"{len(_ARTICLES.get(route, []))} articles"
                                        ),
                                        key=f"section-count-{route}",
                                        style=Style(
                                            font_size=13.0,
                                            color=ON_MUTED,
                                        ),
                                    ),
                                ],
                            ),
                            Button(
                                label="→",
                                on_click=make_section_handler(label, route),
                                key=f"section-btn-{route}",
                                style=Style(
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=16.0
                                    ),
                                    radius=8.0,
                                    background=ACCENT,
                                    color=ON_SURFACE,
                                    font_size=16.0,
                                ),
                            ),
                        ],
                    ),
                ],
            )
        )

    return Column(
        key="home-body",
        style=Style(gap=16.0, padding=Edge.all(24.0), background=BACKGROUND),
        children=[
            Text(
                content="Browse the documentation by section or open the drawer.",
                key="home-intro",
                style=Style(font_size=15.0, color=ON_MUTED),
            ),
            *section_cards,
        ],
    )
```

### 4.4 Despachante de rota

```python
def _screen_for_route(
    route: Route,
    app: App[DrawerNavState],
) -> Widget:
    """Return the content widget for the given route.

    Args:
        route: The current top-of-stack route.
        app: The application handle.

    Returns:
        The content widget matching route.name.
    """
    if route.name == "/":
        return _home_body(app)
    segments = [s for s in route.name.split("/") if s]
    if len(segments) == 1:
        return _section_body(route.name, app)
    return _article_body(route.name)
```

A lógica é simples:

| `route.name`                    | Segmentos | Renderiza          |
| ------------------------------- | --------- | ------------------ |
| `"/"`                           | 0         | Tela inicial       |
| `"/getting-started"`            | 1         | Índice de seção    |
| `"/getting-started/quickstart"` | 2         | Corpo do artigo    |

---

## 5. O painel do drawer

O drawer lista todas as seções.  Tocar em uma delas executa `app.reset()` para
substituir toda a pilha de uma vez, e fecha o drawer.

```python
def _drawer_panel(app: App[DrawerNavState]) -> Widget:
    """Build the drawer side panel with section navigation links.

    Args:
        app: The application handle.

    Returns:
        A Column acting as the drawer panel content.
    """

    def make_drawer_nav(label: str, route: str) -> Callable[[], None]:
        """Build a drawer navigation handler for route."""

        def handler() -> None:
            """Navigate to section and close drawer."""
            app.reset([Route(name="/"), Route(name=route)])

            def _update(s: DrawerNavState) -> None:
                s.history_labels[:] = ["Home", label]
                s.drawer_open = False

            app.set_state(_update)

        return handler

    nav_items: list[Widget] = []
    current_route = app.nav.top.name
    for label, route in _SECTIONS:
        active = current_route == route or current_route.startswith(route + "/")
        nav_items.append(
            Button(
                label=label,
                on_click=make_drawer_nav(label, route),
                key=f"drawer-nav-{route}",
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

    def go_home() -> None:
        """Reset to the root route and close the drawer."""
        app.reset([Route(name="/")])

        def _reset_home(s: DrawerNavState) -> None:
            s.history_labels[:] = ["Home"]
            s.drawer_open = False

        app.set_state(_reset_home)

    return Column(
        key="drawer-panel",
        style=Style(
            width=260.0,
            padding=Edge.all(16.0),
            gap=8.0,
            background=SURFACE,
        ),
        children=[
            Text(
                content="tempestweb",
                key="drawer-brand",
                style=Style(
                    font_size=18.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
            ),
            Text(
                content="Documentation",
                key="drawer-subtitle",
                style=Style(font_size=12.0, color=ON_MUTED),
            ),
            Divider(key="drawer-div-top"),
            Button(
                label="Home",
                on_click=go_home,
                key="drawer-home-btn",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=12.0),
                    radius=8.0,
                    background=Color.from_hex("#00000000"),
                    color=ON_MUTED,
                    font_size=14.0,
                ),
            ),
            Divider(key="drawer-div-sections"),
            *nav_items,
        ],
    )
```

!!! info "Por que `app.reset()` em vez de `app.push()`?"
    `app.push` **empilha** uma rota sobre as existentes.  Se o usuário navegou
    para `"/getting-started/installation"` e então tocar em **Deployment** no
    drawer, não queremos acumular rotas — queremos substituir tudo.
    `app.reset([Route("/"), Route("/deployment")])` substitui a pilha inteira de
    uma vez e o reconciliador emite um único patch.

---

## 6. A `view` principal

Agora montamos tudo.  A `view` é a função que o tempestweb chama a cada rebuild.

```python
def view(app: App[DrawerNavState]) -> Widget:
    """Render the full drawer-navigation app from the current state.

    Args:
        app: The application handle exposing state, nav, and the
            navigation mutators.

    Returns:
        The widget tree for the current state.
    """
    current_route = app.nav.top
    stack_depth = len(app.nav.stack)

    # --- handlers ---

    def toggle_drawer() -> None:
        """Toggle the navigation drawer open or closed."""
        app.set_state(lambda s: setattr(s, "drawer_open", not s.drawer_open))

    def on_drawer_change() -> None:
        """Close the drawer when the renderer signals it should close."""
        app.set_state(lambda s: setattr(s, "drawer_open", False))

    def make_crumb_handler(crumb_index: int) -> Callable[[], None]:
        """Build a breadcrumb handler that pops back to crumb_index."""

        def handler() -> None:
            """Pop the nav stack back to crumb_index and trim the crumb labels."""
            new_stack = list(app.nav.stack[: crumb_index + 1])
            app.reset(new_stack)
            app.set_state(
                lambda s: s.history_labels.__setitem__(
                    slice(None), s.history_labels[: crumb_index + 1]
                )
            )

        return handler

    # --- breadcrumb ---

    crumb_labels = list(app.state.history_labels)
    breadcrumb = Breadcrumb(
        key="main-breadcrumb",
        items=crumb_labels,
        separator="›",
        on_select=lambda idx: make_crumb_handler(idx)(),
    )

    # --- appbar ---

    back_button: Widget | None = None
    if app.nav.can_pop:

        def go_back() -> None:
            """Pop the current route and trim the breadcrumb."""
            app.pop()

            def _trim(s: DrawerNavState) -> None:
                if len(s.history_labels) > 1:
                    s.history_labels.pop()

            app.set_state(_trim)

        back_button = Button(
            label="←",
            on_click=go_back,
            key="back-btn",
            style=Style(
                padding=Edge.all(8.0),
                radius=6.0,
                background=MUTED,
                color=ON_SURFACE,
                font_size=16.0,
            ),
        )

    burger = Button(
        label="☰",
        on_click=toggle_drawer,
        key="burger-btn",
        style=Style(
            padding=Edge.all(8.0),
            radius=6.0,
            background=MUTED,
            color=ON_SURFACE,
            font_size=16.0,
        ),
    )

    leading_widget: Widget = back_button if back_button is not None else burger

    depth_text = Text(
        content=f"depth: {stack_depth}",
        key="depth-badge",
        style=Style(
            font_size=12.0,
            color=ON_MUTED,
            padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
            radius=6.0,
            background=MUTED,
        ),
    )

    appbar = AppBar(
        key="main-appbar",
        title=crumb_labels[-1] if crumb_labels else "Home",
        leading=leading_widget,
        actions=[depth_text],
    )

    # --- barra de breadcrumb ---

    breadcrumb_bar = Container(
        key="breadcrumb-bar",
        style=Style(
            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
            background=SURFACE,
        ),
        child=breadcrumb,
    )

    # --- conteúdo da tela via despachante ---

    screen_content = _screen_for_route(current_route, app)

    navigator_widget = Container(
        key="navigator-host",
        style=Style(grow=1.0, background=BACKGROUND),
        child=screen_content,
    )

    # --- drawer ---

    drawer_panel = _drawer_panel(app)

    route_drawer = RouteDrawer(
        key="main-drawer",
        child=navigator_widget,
        drawer=drawer_panel,
        open=app.state.drawer_open,
        on_change=on_drawer_change,
    )

    # --- scaffold completo ---

    top_area = Column(
        key="top-area",
        style=Style(gap=0.0),
        children=[appbar, breadcrumb_bar],
    )

    return Scaffold(
        key="root-scaffold",
        app_bar=top_area,
        body=route_drawer,
    )
```

Vamos destrinchar os pontos principais:

### 6.1 `app.nav.can_pop` — hambúrguer ou seta

```python
leading_widget: Widget = back_button if back_button is not None else burger
```

Quando `app.nav.can_pop` for `True` (há mais de uma rota na pilha), mostramos
`"←"` para voltar.  Caso contrário, mostramos `"☰"` para abrir o drawer.  O
reconciliador troca os dois com um único patch `replace`.

### 6.2 `Breadcrumb` com `on_select`

```python
breadcrumb = Breadcrumb(
    key="main-breadcrumb",
    items=crumb_labels,
    separator="›",
    on_select=lambda idx: make_crumb_handler(idx)(),
)
```

`on_select` recebe o índice do item clicado.  `make_crumb_handler(idx)` faz
`app.reset` com apenas os primeiros `idx + 1` elementos da pilha, efetivamente
"popando" múltiplos níveis de uma vez.

### 6.3 `RouteDrawer` com `open` e `on_change`

```python
route_drawer = RouteDrawer(
    key="main-drawer",
    child=navigator_widget,
    drawer=drawer_panel,
    open=app.state.drawer_open,
    on_change=on_drawer_change,
)
```

`open` é controlado pelo estado — nunca pelo drawer em si.  `on_change` é
chamado pelo renderer quando o usuário fecha o drawer clicando fora dele, e
sincroniza o estado.

---

## 7. Guarda de smoke-test

```python
if __name__ == "__main__":
    _app: App[DrawerNavState] = App(
        state=make_state(),
        view=view,
        apply_patches=lambda p: None,
        nav=NavStack(),
    )
    _node = build(view(_app))
    assert _node.type and _node.children, "smoke-test failed"
    print("smoke-test OK", _node.type, len(_node.children))
```

Execute `python examples/router-drawer/app.py` para confirmar que a árvore de
widgets é construída sem erros antes de rodar no browser.

---

## 8. Execute o app 🚀

**Modo A — Python no browser (Pyodide):**

```bash
tempestweb dev --mode wasm --path examples/router-drawer
```

**Modo B — Python no servidor (FastAPI + WebSocket):**

```bash
tempestweb dev --mode server --path examples/router-drawer
```

Abra `http://localhost:8000` e:

1. ✅ Toque em qualquer card de seção — a rota muda, o breadcrumb cresce.
2. ✅ Toque em `"→"` num artigo — você entra no segundo nível.
3. ✅ Toque em qualquer crumb — a pilha retrocede ao ponto clicado.
4. ✅ Abra o drawer (`"☰"`) e escolha outra seção — a pilha é substituída.

!!! check "Verificação dos checks"
    Antes de commitar, rode:

    ```bash
    ruff check . && ruff format --check .
    mypy tempestweb
    pytest -q
    ```

    Todos os quatro checks devem passar em verde ✅.

---

## Recapitulando

Neste tutorial você aprendeu:

- **`RouteDrawer`** — painel lateral controlado por `open` (flag de estado) e
  fechado via `on_change`.
- **`app.push(Route(...))`** — empilha uma rota e agenda um rebuild.
- **`app.pop()`** — desfaz o último push; `app.nav.can_pop` indica se é possível.
- **`app.reset([...])`** — substitui a pilha inteira, ideal para navegação pelo
  drawer.
- **`Breadcrumb`** com `on_select` — permite saltar de volta a qualquer nível
  sem chamar `pop` múltiplas vezes manualmente.
- **Closures para handlers em loops** — padrão `make_xxx_handler(arg)` para
  capturar variáveis corretamente.

---

## Próximos passos

- Veja [Dashboard Shell](dashboard-shell.md) para um layout mais elaborado com
  `NavBar` e múltiplos painéis.
- Explore [Tabs & Perfil](tabs-profile.md) para navegação por abas em vez de
  drawer.
- Leia [Modos de Execução](../tutorial/modes.md) para entender as diferenças
  entre Modo A e Modo B em produção.
