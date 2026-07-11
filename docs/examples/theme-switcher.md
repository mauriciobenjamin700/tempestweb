# Theme Switcher — Alternador de Tema Claro/Escuro 🚀

Construa um alternador completo de tema claro/escuro com seletor de cores de destaque — e aprenda a gerenciar o sistema de temas do tempestweb com `App.set_theme`, `Theme.is_dark` e `ThemeChangeEvent`.

---

## O que você vai construir

Um painel de controle de temas com cinco seções:

- 🏷 **Header** — badge com o modo ativo e a cor de destaque selecionada
- ☀️/🌙 **Colour Mode** — botões Light / System / Dark + switch de simulação do SO
- 🎨 **Accent Colour** — três swatches de cor (Azul, Violeta, Teal)
- 🪟 **Colour Tokens** — prévia dos tokens semânticos da paleta atual
- 🔔 **ThemeChangeEvent** — log de eventos do SO com botões para disparar manualmente

!!! note "Nota — transição suave"
    Todos os `Container` usam `Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)`.
    O renderizador interpola a cor de fundo entre as trocas de tema, tornando a
    alternância visualmente polida sem nenhum código extra na lógica do app.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada antes de continuar:

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

```bash
mkdir -p examples/theme-switcher
touch examples/theme-switcher/app.py
```

---

## Passo 1 — Definindo o estado

O estado deste app rastreia três coisas:

| Campo | Tipo | Significado |
|---|---|---|
| `forced_mode` | `ThemeMode` | Modo que o usuário escolheu explicitamente (`LIGHT`, `DARK` ou `SYSTEM`) |
| `last_os_event` | `str` | Descrição textual do último `ThemeChangeEvent` recebido |
| `swatch_index` | `int` | Índice do swatch de destaque ativo (0=Azul, 1=Violeta, 2=Teal) |

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core.theme import ThemeMode


@dataclass
class ThemeSwitcherState:
    """Application state for the theme-switcher demo.

    Attributes:
        forced_mode: The ThemeMode the user has explicitly chosen;
            SYSTEM means follow the OS.
        last_os_event: A human-readable description of the last
            ThemeChangeEvent received from the OS (purely for display).
        swatch_index: Index of the accent colour swatch the user last clicked
            (0 = blue, 1 = violet, 2 = teal).
    """

    forced_mode: ThemeMode = ThemeMode.SYSTEM
    last_os_event: str = "none yet"
    swatch_index: int = 0


def make_state() -> ThemeSwitcherState:
    """Build the initial application state.

    Returns:
        A fresh ThemeSwitcherState with SYSTEM mode and blue accent.
    """
    return ThemeSwitcherState()
```

!!! tip "Dica — `ThemeMode.SYSTEM`"
    Com `ThemeMode.SYSTEM`, o tempestweb delega a decisão ao SO. O método
    `Theme.is_dark(platform_dark_mode=...)` resolve isso corretamente — você não
    precisa detectar o esquema manualmente.

---

## Passo 2 — Definindo as paletas

Defina duas paletas de cores (clara e escura) como constantes no topo do arquivo.
Isso mantém todos os valores de cor centralizados e facilita a manutenção.

```python
from tempest_core.style import Color, Curve, Transition

# Light palette
_LIGHT_BG: Color = Color.from_hex("#f8fafc")
_LIGHT_SURFACE: Color = Color.from_hex("#ffffff")
_LIGHT_ON_BG: Color = Color.from_hex("#0f172a")
_LIGHT_MUTED: Color = Color.from_hex("#64748b")
_LIGHT_DIVIDER: Color = Color.from_hex("#e2e8f0")
_LIGHT_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_LIGHT_SUCCESS: Color = Color.from_hex("#16a34a")
_LIGHT_WARN: Color = Color.from_hex("#d97706")
_LIGHT_ERROR: Color = Color.from_hex("#dc2626")

# Dark palette
_DARK_BG: Color = Color.from_hex("#0b0f14")
_DARK_SURFACE: Color = Color.from_hex("#1e293b")
_DARK_ON_BG: Color = Color.from_hex("#f1f5f9")
_DARK_MUTED: Color = Color.from_hex("#94a3b8")
_DARK_DIVIDER: Color = Color.from_hex("#334155")
_DARK_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_DARK_SUCCESS: Color = Color.from_hex("#4ade80")
_DARK_WARN: Color = Color.from_hex("#fbbf24")
_DARK_ERROR: Color = Color.from_hex("#f87171")

# Transição suave para containers de fundo/superfície
_TWEEN: Transition = Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)

# Cor transparente para o anel do swatch não selecionado
_TRANSPARENT: Color = Color(r=0, g=0, b=0, a=0.0)
```

Defina também as três paletas de cores de destaque:

```python
_ACCENT_LIGHT: list[Color] = [
    Color.from_hex("#2563eb"),  # blue
    Color.from_hex("#7c3aed"),  # violet
    Color.from_hex("#0d9488"),  # teal
]
_ACCENT_DARK: list[Color] = [
    Color.from_hex("#3b82f6"),  # blue
    Color.from_hex("#a78bfa"),  # violet
    Color.from_hex("#2dd4bf"),  # teal
]
_ACCENT_NAMES: list[str] = ["Blue", "Violet", "Teal"]
```

!!! info "Nota — tokens semânticos"
    O nome dos campos (`background`, `surface`, `on_background`, `error`) espelha
    os tokens semânticos do Material Design. Usar nomes semânticos (em vez de
    `cor_azul_escuro`) torna a paleta legível independente do esquema ativo.

---

## Passo 3 — Helpers de resolução de tema

Dois pequenos helpers isolam a lógica de resolução de tema do resto da UI:

```python
from tempest_core import App
from tempest_core.style import Color
from tempest_core.theme import Theme, ThemeMode


def _is_dark(app: App[ThemeSwitcherState]) -> bool:
    """Resolve whether the current theme renders dark.

    Delegates to Theme.is_dark so SYSTEM is resolved correctly against
    the platform flag.

    Args:
        app: The application handle exposing theme and media.

    Returns:
        True when the resolved scheme is dark.
    """
    return app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)


def _accent(app: App[ThemeSwitcherState], dark: bool) -> Color:
    """Return the currently selected accent colour for the given scheme.

    Args:
        app: The application handle exposing state.
        dark: Whether the dark palette should be used.

    Returns:
        The Color for the active accent.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    return palette[app.state.swatch_index]
```

O helper `_make_theme` constrói um `Theme` completo toda vez que o modo ou o
swatch mudar:

```python
def _make_theme(
    mode: ThemeMode,
    dark: bool,
    swatch_index: int,
) -> Theme:
    """Construct a fully-populated Theme.

    Args:
        mode: The ThemeMode to set.
        dark: Whether the dark palette should be used.
        swatch_index: The 0-based index into the accent colour lists.

    Returns:
        The fully-populated Theme.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    accent_color: Color = palette[swatch_index]
    return Theme(
        mode=mode,
        primary=accent_color,
        background=_DARK_BG if dark else _LIGHT_BG,
        surface=_DARK_SURFACE if dark else _LIGHT_SURFACE,
        on_primary=_DARK_ON_PRIMARY if dark else _LIGHT_ON_PRIMARY,
        on_background=_DARK_ON_BG if dark else _LIGHT_ON_BG,
        error=_DARK_ERROR if dark else _LIGHT_ERROR,
    )
```

!!! tip "Dica — `app.set_theme` vs `app.set_state`"
    Chame sempre os dois juntos quando o modo mudar:
    `app.set_state(...)` atualiza o campo `forced_mode` do seu estado local
    (para destacar o botão ativo), enquanto `app.set_theme(...)` propaga o
    novo `Theme` para toda a árvore de widgets via o reconciliador.

---

## Passo 4 — O card de cabeçalho

O primeiro card exibe o modo ativo e o nome do destaque atual:

```python
from tempest_core import Style, Widget
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Button, Column, Container, Row, Switch, Text


def _header_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the header card showing the current active theme.

    Args:
        app: The application handle.

    Returns:
        A padded container with the title, active mode label and accent badge.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    accent_color: Color = _accent(app, dark)

    mode_label: str
    if app.state.forced_mode is ThemeMode.DARK:
        mode_label = "Dark"
    elif app.state.forced_mode is ThemeMode.LIGHT:
        mode_label = "Light"
    else:
        resolved: str = "dark" if dark else "light"
        mode_label = f"System ({resolved})"

    accent_name: str = _ACCENT_NAMES[app.state.swatch_index]

    return Container(
        key="header-card",
        style=Style(
            background=surface,
            padding=Edge.all(24.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Theme Switcher",
                    key="header-title",
                    style=Style(
                        font_size=26.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Text(
                    content=f"Active mode: {mode_label}  •  Accent: {accent_name}",
                    key="header-subtitle",
                    style=Style(font_size=14.0, color=muted),
                ),
                Container(
                    key="accent-badge",
                    style=Style(
                        background=accent_color,
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=20.0,
                        align=AlignItems.CENTER,
                        width=160.0,
                    ),
                    child=Text(
                        content="Live colour token",
                        key="badge-text",
                        style=Style(
                            font_size=12.0,
                            font_weight=FontWeight.BOLD,
                            color=_DARK_ON_BG,
                        ),
                    ),
                ),
            ],
        ),
    )
```

Perceba como cada cor é **lida diretamente da paleta** a cada chamada de `view`.
Não há cache nem variável global de "cor atual" — o tempestweb chama `view`
novamente após cada `set_theme`, e a função simplesmente resolve a paleta certa.

---

## Passo 5 — O card de modo com o switch de SO

O segundo card traz os três botões de modo e um `Switch` que simula o sinal do SO:

```python
from tempest_core.style import Border, JustifyContent
from tempest_core.theme import MediaQueryData
from tempest_core.widgets.events import ToggleEvent


def _mode_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the mode-selection card with Light / System / Dark buttons.

    Args:
        app: The application handle.

    Returns:
        A container with three mode buttons and the OS dark-mode toggle.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    def _apply_mode(new_mode: ThemeMode) -> None:
        """Switch to the requested theme mode."""
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        app.set_state(lambda s: setattr(s, "forced_mode", new_mode))
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def set_light() -> None:
        """Force the light colour scheme."""
        _apply_mode(ThemeMode.LIGHT)

    def set_system() -> None:
        """Follow the operating system colour scheme."""
        _apply_mode(ThemeMode.SYSTEM)

    def set_dark() -> None:
        """Force the dark colour scheme."""
        _apply_mode(ThemeMode.DARK)

    def _btn_style(mode: ThemeMode) -> Style:
        """Build a button-wrapper style, highlighted when the mode is active."""
        is_active: bool = app.state.forced_mode is mode
        return Style(
            background=accent_color if is_active else surface,
            border=Border(
                width=2.0,
                color=accent_color if is_active else divider,
            ),
            radius=10.0,
            padding=Edge.symmetric(vertical=6.0, horizontal=14.0),
            transition=_TWEEN,
        )

    def _on_change_os(event: ToggleEvent) -> None:
        """Handle the OS dark-mode indicator toggle (simulation).

        Args:
            event: The toggle event carrying the new checked state.
        """
        new_media: MediaQueryData = app.media.model_copy(
            update={"platform_dark_mode": event.checked}
        )
        app._update_media(new_media)  # noqa: SLF001

    return Container(
        key="mode-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Mode",
                    key="mode-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="mode-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="mode-buttons",
                    style=Style(gap=8.0, justify=JustifyContent.CENTER),
                    children=[
                        Container(
                            key="btn-light-wrap",
                            style=_btn_style(ThemeMode.LIGHT),
                            child=Button(
                                label="Light",
                                on_click=set_light,
                                key="btn-light",
                            ),
                        ),
                        Container(
                            key="btn-system-wrap",
                            style=_btn_style(ThemeMode.SYSTEM),
                            child=Button(
                                label="System",
                                on_click=set_system,
                                key="btn-system",
                            ),
                        ),
                        Container(
                            key="btn-dark-wrap",
                            style=_btn_style(ThemeMode.DARK),
                            child=Button(
                                label="Dark",
                                on_click=set_dark,
                                key="btn-dark",
                            ),
                        ),
                    ],
                ),
                Row(
                    key="os-row",
                    style=Style(gap=12.0, align=AlignItems.CENTER),
                    children=[
                        Text(
                            content="Simulate OS dark mode",
                            key="os-label",
                            style=Style(font_size=14.0, color=muted, grow=1.0),
                        ),
                        Switch(
                            checked=app.media.platform_dark_mode,
                            on_change=_on_change_os,
                            key="os-switch",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "(Only affects SYSTEM mode. Mirrors how "
                        "the host fires ThemeChangeEvent.)"
                    ),
                    key="os-hint",
                    style=Style(font_size=11.0, color=muted),
                ),
            ],
        ),
    )
```

!!! info "Nota — `app._update_media`"
    Em produção, o host (browser ou servidor) atualiza `MediaQueryData`
    automaticamente quando o SO muda de esquema. Aqui usamos `_update_media`
    diretamente para simular essa notificação no demo — isso permite testar o
    comportamento de `SYSTEM` sem precisar mudar as preferências do sistema
    operacional.

---

## Passo 6 — O seletor de destaque

O terceiro card cria swatches clicáveis para trocar a cor de destaque sem mudar
o modo claro/escuro. O truque está na factory `_make_swatch_handler` que captura
o índice correto em um closure:

```python
from collections.abc import Callable


def _accent_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the accent-colour picker card.

    Args:
        app: The application handle.

    Returns:
        A container with three selectable swatch buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    swatch_colors: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT

    def _make_swatch_handler(idx: int) -> Callable[[], None]:
        """Return a click handler that selects accent swatch at idx.

        Args:
            idx: The 0-based index into the accent colour list.

        Returns:
            A zero-argument callable that applies the selected swatch.
        """

        def handler() -> None:
            """Select the accent swatch at the captured index."""
            app.set_state(lambda s: setattr(s, "swatch_index", idx))
            app.set_theme(_make_theme(app.state.forced_mode, dark, idx))

        return handler

    swatch_widgets: list[Widget] = []
    for i, (color, name) in enumerate(zip(swatch_colors, _ACCENT_NAMES, strict=True)):
        is_selected: bool = app.state.swatch_index == i
        swatch_widgets.append(
            Column(
                key=f"swatch-col-{i}",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Container(
                        key=f"swatch-{i}",
                        style=Style(
                            width=44.0,
                            height=44.0,
                            radius=22.0,
                            background=color,
                            border=Border(
                                width=3.0,
                                color=on_bg if is_selected else _TRANSPARENT,
                            ),
                            transition=_TWEEN,
                        ),
                        child=Button(
                            label="",
                            on_click=_make_swatch_handler(i),
                            key=f"swatch-btn-{i}",
                        ),
                    ),
                    Text(
                        content=name,
                        key=f"swatch-label-{i}",
                        style=Style(
                            font_size=11.0,
                            color=on_bg if is_selected else muted,
                            font_weight=(FontWeight.BOLD if is_selected else None),
                        ),
                    ),
                ],
            )
        )

    return Container(
        key="accent-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Accent Colour",
                    key="accent-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="accent-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="swatches-row",
                    style=Style(
                        gap=24.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=swatch_widgets,
                ),
            ],
        ),
    )
```

!!! warning "Aviso — closures em loops"
    Sempre use uma factory (`_make_swatch_handler(i)`) ao criar handlers
    dentro de um `for`. Um lambda direto (`lambda: handler_para(i)`) captura
    `i` por referência, então todos os botões acabam chamando o handler do
    **último** índice. A factory captura `idx` por valor no momento da chamada.

---

## Passo 7 — Preview de tokens e evento de SO

Os dois últimos cards completam o app.

O card de **Colour Tokens** exibe uma fila de chips coloridos com os tokens
semânticos da paleta atual:

```python
def _palette_preview_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render a colour-token preview strip.

    Args:
        app: The application handle.

    Returns:
        A container with labelled colour chips for every semantic token.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    tokens: list[tuple[str, Color]] = [
        ("Background", _DARK_BG if dark else _LIGHT_BG),
        ("Surface", _DARK_SURFACE if dark else _LIGHT_SURFACE),
        ("On-BG", _DARK_ON_BG if dark else _LIGHT_ON_BG),
        ("Muted", _DARK_MUTED if dark else _LIGHT_MUTED),
        ("Primary", accent_color),
        ("Success", _DARK_SUCCESS if dark else _LIGHT_SUCCESS),
        ("Warning", _DARK_WARN if dark else _LIGHT_WARN),
        ("Error", _DARK_ERROR if dark else _LIGHT_ERROR),
    ]

    chips: list[Widget] = [
        Column(
            key=f"chip-col-{label}",
            style=Style(gap=4.0, align=AlignItems.CENTER),
            children=[
                Container(
                    key=f"chip-{label}",
                    style=Style(
                        width=36.0,
                        height=36.0,
                        radius=8.0,
                        background=color,
                        border=Border(width=1.0, color=divider),
                        transition=_TWEEN,
                    ),
                ),
                Text(
                    content=label,
                    key=f"chip-label-{label}",
                    style=Style(font_size=10.0, color=muted),
                ),
            ],
        )
        for label, color in tokens
    ]

    return Container(
        key="palette-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Tokens",
                    key="palette-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="palette-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="chips-row",
                    style=Style(
                        gap=12.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=chips,
                ),
            ],
        ),
    )
```

O card de **ThemeChangeEvent** simula notificações do sistema operacional:

```python
from tempest_core.widgets.events import ThemeChangeEvent


def _os_event_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the OS-event log card.

    Args:
        app: The application handle.

    Returns:
        A container with the last OS event description and fire buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    success: Color = _DARK_SUCCESS if dark else _LIGHT_SUCCESS

    def _handle_theme_change_event(event: ThemeChangeEvent) -> None:
        """Handle an OS-level theme change notification.

        Args:
            event: The typed event carrying the new ThemeMode.
        """
        new_mode: ThemeMode = event.mode
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        log_msg: str = f"ThemeChangeEvent(mode={new_mode!r})"

        def _mutate(s: ThemeSwitcherState) -> None:
            s.forced_mode = new_mode
            s.last_os_event = log_msg

        app.set_state(_mutate)
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def _fire_dark_event() -> None:
        """Simulate an OS dark-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.DARK))

    def _fire_light_event() -> None:
        """Simulate an OS light-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.LIGHT))

    return Container(
        key="os-event-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="ThemeChangeEvent (OS simulation)",
                    key="event-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="event-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Text(
                    content=f"Last event: {app.state.last_os_event}",
                    key="event-log",
                    style=Style(font_size=13.0, color=muted),
                ),
                Row(
                    key="event-buttons",
                    style=Style(gap=8.0),
                    children=[
                        Button(
                            label="Fire dark event",
                            on_click=_fire_dark_event,
                            key="fire-dark",
                        ),
                        Button(
                            label="Fire light event",
                            on_click=_fire_light_event,
                            key="fire-light",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "Simulates the host bridge dispatching "
                        "ThemeChangeEvent to App.set_theme."
                    ),
                    key="event-hint",
                    style=Style(font_size=11.0, color=success),
                ),
            ],
        ),
    )
```

!!! info "Nota — `ThemeChangeEvent` em produção"
    Em um app real, o host (browser ou servidor) dispara `ThemeChangeEvent`
    automaticamente quando o SO muda de esquema — você só precisa registrar o
    handler. Aqui os botões simulam essa notificação para que o exemplo seja
    completamente auto-contido.

---

## Passo 8 — Montando a função `view`

A função raiz `view` compõe os cinco cards em uma `Column`:

```python
from tempest_core import App, Style, Widget
from tempest_core.style import Edge


def view(app: App[ThemeSwitcherState]) -> Widget:
    """Render the full theme-switcher UI.

    All sections read app.theme.is_dark() (resolved against
    app.media.platform_dark_mode) to select the correct palette, so the
    entire tree restyles on every set_theme call.

    Args:
        app: The application handle exposing state, theme and media.

    Returns:
        The widget tree for the current state and theme.
    """
    dark: bool = _is_dark(app)
    bg: Color = _DARK_BG if dark else _LIGHT_BG

    return Container(
        key="root",
        style=Style(
            background=bg,
            padding=Edge.all(0.0),
            transition=_TWEEN,
        ),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _header_card(app),
                _mode_card(app),
                _accent_card(app),
                _palette_preview_card(app),
                _os_event_card(app),
            ],
        ),
    )
```

---

## O app completo

Aqui está o arquivo completo `examples/theme-switcher/app.py`, pronto para copiar:

```python
"""Theme switcher — demonstrates light/dark theming via ``App.set_theme``.

The app maintains its own colour palette for both schemes inside ``view`` and
calls ``app.set_theme`` to swap between them.  Every container, text and button
re-reads ``app.theme.is_dark()`` on each rebuild so the entire tree restyles
without any patch other than ``Update`` on the changed ``Style`` fields — no
navigation, no overlays, just pure theming.

Key concepts shown
------------------
* :class:`~tempest_core.theme.Theme` — carries the active
  :class:`~tempest_core.theme.ThemeMode` plus an optional colour palette.
* :meth:`~tempest_core.core.state.App.set_theme` — swaps the active theme
  and schedules a coalesced rebuild like any state mutation.
* :meth:`~tempest_core.theme.Theme.is_dark` — resolves ``SYSTEM`` against
  the platform flag; used by the ``view`` to pick the right palette at
  build time.
* :class:`~tempest_core.widgets.events.ThemeChangeEvent` — the typed event
  the host fires when the OS colour scheme changes; shown here as an inline
  handler the user can fire manually.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.style import (
    AlignItems,
    Border,
    Color,
    Curve,
    Edge,
    FontWeight,
    JustifyContent,
    Transition,
)
from tempest_core.theme import MediaQueryData, Theme, ThemeMode
from tempest_core.widgets import Button, Column, Container, Row, Switch, Text
from tempest_core.widgets.events import ThemeChangeEvent, ToggleEvent

# ---------------------------------------------------------------------------
# Palette definitions
# ---------------------------------------------------------------------------

# Light palette
_LIGHT_BG: Color = Color.from_hex("#f8fafc")
_LIGHT_SURFACE: Color = Color.from_hex("#ffffff")
_LIGHT_ON_BG: Color = Color.from_hex("#0f172a")
_LIGHT_MUTED: Color = Color.from_hex("#64748b")
_LIGHT_DIVIDER: Color = Color.from_hex("#e2e8f0")
_LIGHT_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_LIGHT_SUCCESS: Color = Color.from_hex("#16a34a")
_LIGHT_WARN: Color = Color.from_hex("#d97706")
_LIGHT_ERROR: Color = Color.from_hex("#dc2626")

# Dark palette
_DARK_BG: Color = Color.from_hex("#0b0f14")
_DARK_SURFACE: Color = Color.from_hex("#1e293b")
_DARK_ON_BG: Color = Color.from_hex("#f1f5f9")
_DARK_MUTED: Color = Color.from_hex("#94a3b8")
_DARK_DIVIDER: Color = Color.from_hex("#334155")
_DARK_ON_PRIMARY: Color = Color.from_hex("#ffffff")
_DARK_SUCCESS: Color = Color.from_hex("#4ade80")
_DARK_WARN: Color = Color.from_hex("#fbbf24")
_DARK_ERROR: Color = Color.from_hex("#f87171")

# Smooth implicit transition applied to background/surface containers when the
# theme changes — the renderer tweens the colour so the switch feels polished.
_TWEEN: Transition = Transition(duration_ms=200, curve=Curve.EASE_IN_OUT)

# Transparent colour for the unselected swatch ring.
_TRANSPARENT: Color = Color(r=0, g=0, b=0, a=0.0)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class ThemeSwitcherState:
    """Application state for the theme-switcher demo.

    Attributes:
        forced_mode: The :class:`~tempest_core.theme.ThemeMode` the user
            has explicitly chosen; ``SYSTEM`` means follow the OS.
        last_os_event: A human-readable description of the last
            ``ThemeChangeEvent`` received from the OS (purely for display).
        swatch_index: Index of the accent colour swatch the user last clicked
            (0 = blue, 1 = violet, 2 = teal), to showcase per-palette
            customisation on top of the dark/light split.
    """

    forced_mode: ThemeMode = ThemeMode.SYSTEM
    last_os_event: str = "none yet"
    swatch_index: int = 0


def make_state() -> ThemeSwitcherState:
    """Build the initial application state.

    Returns:
        A fresh :class:`ThemeSwitcherState` with ``SYSTEM`` mode and blue
        accent.
    """
    return ThemeSwitcherState()


# ---------------------------------------------------------------------------
# Accent swatches (three selectable accent palettes)
# ---------------------------------------------------------------------------

_ACCENT_LIGHT: list[Color] = [
    Color.from_hex("#2563eb"),  # blue
    Color.from_hex("#7c3aed"),  # violet
    Color.from_hex("#0d9488"),  # teal
]
_ACCENT_DARK: list[Color] = [
    Color.from_hex("#3b82f6"),  # blue
    Color.from_hex("#a78bfa"),  # violet
    Color.from_hex("#2dd4bf"),  # teal
]
_ACCENT_NAMES: list[str] = ["Blue", "Violet", "Teal"]


# ---------------------------------------------------------------------------
# Helper: resolve dark flag from app context
# ---------------------------------------------------------------------------


def _is_dark(app: App[ThemeSwitcherState]) -> bool:
    """Resolve whether the current theme renders dark.

    Delegates to :meth:`~tempest_core.theme.Theme.is_dark` so ``SYSTEM``
    is resolved correctly against the platform flag.

    Args:
        app: The application handle exposing ``theme`` and ``media``.

    Returns:
        ``True`` when the resolved scheme is dark.
    """
    return app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)


def _accent(app: App[ThemeSwitcherState], dark: bool) -> Color:
    """Return the currently selected accent colour for the given scheme.

    Args:
        app: The application handle exposing ``state``.
        dark: Whether the dark palette should be used.

    Returns:
        The :class:`~tempest_core.style.Color` for the active accent.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    return palette[app.state.swatch_index]


def _make_theme(
    mode: ThemeMode,
    dark: bool,
    swatch_index: int,
) -> Theme:
    """Construct a fully-populated :class:`~tempest_core.theme.Theme`.

    Args:
        mode: The :class:`~tempest_core.theme.ThemeMode` to set.
        dark: Whether the dark palette should be used.
        swatch_index: The 0-based index into the accent colour lists.

    Returns:
        The fully-populated :class:`~tempest_core.theme.Theme`.
    """
    palette: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT
    accent_color: Color = palette[swatch_index]
    return Theme(
        mode=mode,
        primary=accent_color,
        background=_DARK_BG if dark else _LIGHT_BG,
        surface=_DARK_SURFACE if dark else _LIGHT_SURFACE,
        on_primary=_DARK_ON_PRIMARY if dark else _LIGHT_ON_PRIMARY,
        on_background=_DARK_ON_BG if dark else _LIGHT_ON_BG,
        error=_DARK_ERROR if dark else _LIGHT_ERROR,
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _header_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the header card showing the current active theme.

    Args:
        app: The application handle.

    Returns:
        A padded container with the title, active mode label and accent badge.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    accent_color: Color = _accent(app, dark)

    mode_label: str
    if app.state.forced_mode is ThemeMode.DARK:
        mode_label = "Dark"
    elif app.state.forced_mode is ThemeMode.LIGHT:
        mode_label = "Light"
    else:
        resolved: str = "dark" if dark else "light"
        mode_label = f"System ({resolved})"

    accent_name: str = _ACCENT_NAMES[app.state.swatch_index]

    return Container(
        key="header-card",
        style=Style(
            background=surface,
            padding=Edge.all(24.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Theme Switcher",
                    key="header-title",
                    style=Style(
                        font_size=26.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Text(
                    content=f"Active mode: {mode_label}  •  Accent: {accent_name}",
                    key="header-subtitle",
                    style=Style(font_size=14.0, color=muted),
                ),
                Container(
                    key="accent-badge",
                    style=Style(
                        background=accent_color,
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=20.0,
                        align=AlignItems.CENTER,
                        width=160.0,
                    ),
                    child=Text(
                        content="Live colour token",
                        key="badge-text",
                        style=Style(
                            font_size=12.0,
                            font_weight=FontWeight.BOLD,
                            color=_DARK_ON_BG,
                        ),
                    ),
                ),
            ],
        ),
    )


def _mode_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the mode-selection card with Light / System / Dark buttons.

    Each button calls App.set_theme with a new Theme built from the chosen
    ThemeMode and active accent palette.

    Args:
        app: The application handle.

    Returns:
        A container with three mode buttons and the OS dark-mode toggle.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    def _apply_mode(new_mode: ThemeMode) -> None:
        """Switch to the requested theme mode.

        Args:
            new_mode: The target ThemeMode.
        """
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        app.set_state(lambda s: setattr(s, "forced_mode", new_mode))
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def set_light() -> None:
        """Force the light colour scheme."""
        _apply_mode(ThemeMode.LIGHT)

    def set_system() -> None:
        """Follow the operating system colour scheme."""
        _apply_mode(ThemeMode.SYSTEM)

    def set_dark() -> None:
        """Force the dark colour scheme."""
        _apply_mode(ThemeMode.DARK)

    def _btn_style(mode: ThemeMode) -> Style:
        """Build a button-wrapper style, highlighted when the mode is active.

        Args:
            mode: The mode this button represents.

        Returns:
            A Style with an accent border when active, or a muted border otherwise.
        """
        is_active: bool = app.state.forced_mode is mode
        return Style(
            background=accent_color if is_active else surface,
            border=Border(
                width=2.0,
                color=accent_color if is_active else divider,
            ),
            radius=10.0,
            padding=Edge.symmetric(vertical=6.0, horizontal=14.0),
            transition=_TWEEN,
        )

    def _on_change_os(event: ToggleEvent) -> None:
        """Handle the OS dark-mode indicator toggle (simulation).

        In a real deployment the renderer fires ThemeChangeEvent; this
        Switch lets the demo simulate that notification by toggling
        media.platform_dark_mode.

        Args:
            event: The toggle event carrying the new checked state.
        """
        new_media: MediaQueryData = app.media.model_copy(
            update={"platform_dark_mode": event.checked}
        )
        app._update_media(new_media)  # noqa: SLF001

    return Container(
        key="mode-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Mode",
                    key="mode-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="mode-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="mode-buttons",
                    style=Style(gap=8.0, justify=JustifyContent.CENTER),
                    children=[
                        Container(
                            key="btn-light-wrap",
                            style=_btn_style(ThemeMode.LIGHT),
                            child=Button(
                                label="Light",
                                on_click=set_light,
                                key="btn-light",
                            ),
                        ),
                        Container(
                            key="btn-system-wrap",
                            style=_btn_style(ThemeMode.SYSTEM),
                            child=Button(
                                label="System",
                                on_click=set_system,
                                key="btn-system",
                            ),
                        ),
                        Container(
                            key="btn-dark-wrap",
                            style=_btn_style(ThemeMode.DARK),
                            child=Button(
                                label="Dark",
                                on_click=set_dark,
                                key="btn-dark",
                            ),
                        ),
                    ],
                ),
                Row(
                    key="os-row",
                    style=Style(gap=12.0, align=AlignItems.CENTER),
                    children=[
                        Text(
                            content="Simulate OS dark mode",
                            key="os-label",
                            style=Style(font_size=14.0, color=muted, grow=1.0),
                        ),
                        Switch(
                            checked=app.media.platform_dark_mode,
                            on_change=_on_change_os,
                            key="os-switch",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "(Only affects SYSTEM mode. Mirrors how "
                        "the host fires ThemeChangeEvent.)"
                    ),
                    key="os-hint",
                    style=Style(font_size=11.0, color=muted),
                ),
            ],
        ),
    )


def _accent_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the accent-colour picker card.

    Three colour swatches (Blue, Violet, Teal) let the user customise the
    accent without changing the dark/light mode.  Selecting a swatch rebuilds
    the full tree with the new accent token.

    Args:
        app: The application handle.

    Returns:
        A container with three selectable swatch buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    swatch_colors: list[Color] = _ACCENT_DARK if dark else _ACCENT_LIGHT

    def _make_swatch_handler(idx: int) -> Callable[[], None]:
        """Return a click handler that selects accent swatch at ``idx``.

        Args:
            idx: The 0-based index into the accent colour list.

        Returns:
            A zero-argument callable that applies the selected swatch.
        """

        def handler() -> None:
            """Select the accent swatch at the captured index."""
            app.set_state(lambda s: setattr(s, "swatch_index", idx))
            app.set_theme(_make_theme(app.state.forced_mode, dark, idx))

        return handler

    swatch_widgets: list[Widget] = []
    for i, (color, name) in enumerate(zip(swatch_colors, _ACCENT_NAMES, strict=True)):
        is_selected: bool = app.state.swatch_index == i
        swatch_widgets.append(
            Column(
                key=f"swatch-col-{i}",
                style=Style(gap=6.0, align=AlignItems.CENTER),
                children=[
                    Container(
                        key=f"swatch-{i}",
                        style=Style(
                            width=44.0,
                            height=44.0,
                            radius=22.0,
                            background=color,
                            border=Border(
                                width=3.0,
                                color=on_bg if is_selected else _TRANSPARENT,
                            ),
                            transition=_TWEEN,
                        ),
                        child=Button(
                            label="",
                            on_click=_make_swatch_handler(i),
                            key=f"swatch-btn-{i}",
                        ),
                    ),
                    Text(
                        content=name,
                        key=f"swatch-label-{i}",
                        style=Style(
                            font_size=11.0,
                            color=on_bg if is_selected else muted,
                            font_weight=(FontWeight.BOLD if is_selected else None),
                        ),
                    ),
                ],
            )
        )

    return Container(
        key="accent-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Accent Colour",
                    key="accent-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="accent-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="swatches-row",
                    style=Style(
                        gap=24.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=swatch_widgets,
                ),
            ],
        ),
    )


def _palette_preview_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render a colour-token preview strip.

    Shows all resolved palette colours (background, surface, text, accent,
    success, warning, error) so the user can see the full scheme at a glance.

    Args:
        app: The application handle.

    Returns:
        A container with labelled colour chips for every semantic token.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    accent_color: Color = _accent(app, dark)

    tokens: list[tuple[str, Color]] = [
        ("Background", _DARK_BG if dark else _LIGHT_BG),
        ("Surface", _DARK_SURFACE if dark else _LIGHT_SURFACE),
        ("On-BG", _DARK_ON_BG if dark else _LIGHT_ON_BG),
        ("Muted", _DARK_MUTED if dark else _LIGHT_MUTED),
        ("Primary", accent_color),
        ("Success", _DARK_SUCCESS if dark else _LIGHT_SUCCESS),
        ("Warning", _DARK_WARN if dark else _LIGHT_WARN),
        ("Error", _DARK_ERROR if dark else _LIGHT_ERROR),
    ]

    chips: list[Widget] = [
        Column(
            key=f"chip-col-{label}",
            style=Style(gap=4.0, align=AlignItems.CENTER),
            children=[
                Container(
                    key=f"chip-{label}",
                    style=Style(
                        width=36.0,
                        height=36.0,
                        radius=8.0,
                        background=color,
                        border=Border(width=1.0, color=divider),
                        transition=_TWEEN,
                    ),
                ),
                Text(
                    content=label,
                    key=f"chip-label-{label}",
                    style=Style(font_size=10.0, color=muted),
                ),
            ],
        )
        for label, color in tokens
    ]

    return Container(
        key="palette-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="Colour Tokens",
                    key="palette-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="palette-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Row(
                    key="chips-row",
                    style=Style(
                        gap=12.0,
                        justify=JustifyContent.CENTER,
                        align=AlignItems.CENTER,
                    ),
                    children=chips,
                ),
            ],
        ),
    )


def _os_event_card(app: App[ThemeSwitcherState]) -> Widget:
    """Render the OS-event log card.

    Args:
        app: The application handle.

    Returns:
        A container with the last OS event description and fire buttons.
    """
    dark: bool = _is_dark(app)
    surface: Color = _DARK_SURFACE if dark else _LIGHT_SURFACE
    on_bg: Color = _DARK_ON_BG if dark else _LIGHT_ON_BG
    muted: Color = _DARK_MUTED if dark else _LIGHT_MUTED
    divider: Color = _DARK_DIVIDER if dark else _LIGHT_DIVIDER
    success: Color = _DARK_SUCCESS if dark else _LIGHT_SUCCESS

    def _handle_theme_change_event(event: ThemeChangeEvent) -> None:
        """Handle an OS-level theme change notification.

        Args:
            event: The typed event carrying the new ThemeMode.
        """
        new_mode: ThemeMode = event.mode
        is_dark_mode: bool = new_mode is ThemeMode.DARK
        log_msg: str = f"ThemeChangeEvent(mode={new_mode!r})"

        def _mutate(s: ThemeSwitcherState) -> None:
            """Apply both mode and log fields in one mutation."""
            s.forced_mode = new_mode
            s.last_os_event = log_msg

        app.set_state(_mutate)
        app.set_theme(_make_theme(new_mode, is_dark_mode, app.state.swatch_index))

    def _fire_dark_event() -> None:
        """Simulate an OS dark-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.DARK))

    def _fire_light_event() -> None:
        """Simulate an OS light-mode ThemeChangeEvent."""
        _handle_theme_change_event(ThemeChangeEvent(mode=ThemeMode.LIGHT))

    return Container(
        key="os-event-card",
        style=Style(
            background=surface,
            padding=Edge.all(20.0),
            radius=16.0,
            transition=_TWEEN,
        ),
        child=Column(
            style=Style(gap=16.0),
            children=[
                Text(
                    content="ThemeChangeEvent (OS simulation)",
                    key="event-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=on_bg,
                    ),
                ),
                Container(
                    key="event-divider",
                    style=Style(height=1.0, background=divider),
                ),
                Text(
                    content=f"Last event: {app.state.last_os_event}",
                    key="event-log",
                    style=Style(font_size=13.0, color=muted),
                ),
                Row(
                    key="event-buttons",
                    style=Style(gap=8.0),
                    children=[
                        Button(
                            label="Fire dark event",
                            on_click=_fire_dark_event,
                            key="fire-dark",
                        ),
                        Button(
                            label="Fire light event",
                            on_click=_fire_light_event,
                            key="fire-light",
                        ),
                    ],
                ),
                Text(
                    content=(
                        "Simulates the host bridge dispatching "
                        "ThemeChangeEvent to App.set_theme."
                    ),
                    key="event-hint",
                    style=Style(font_size=11.0, color=success),
                ),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


def view(app: App[ThemeSwitcherState]) -> Widget:
    """Render the full theme-switcher UI.

    All sections read ``app.theme.is_dark()`` (resolved against
    ``app.media.platform_dark_mode``) to select the correct palette, so the
    entire tree restyles on every :meth:`~App.set_theme` call.

    Args:
        app: The application handle exposing ``state``, ``theme`` and
            ``media``.

    Returns:
        The widget tree for the current state and theme.
    """
    dark: bool = _is_dark(app)
    bg: Color = _DARK_BG if dark else _LIGHT_BG

    return Container(
        key="root",
        style=Style(
            background=bg,
            padding=Edge.all(0.0),
            transition=_TWEEN,
        ),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _header_card(app),
                _mode_card(app),
                _accent_card(app),
                _palette_preview_card(app),
                _os_event_card(app),
            ],
        ),
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/theme-switcher
```

Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/theme-switcher
```

Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica
ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Header com o modo "System (light)" e badge azul "Live colour token"
    2. Card "Colour Mode" com os botões Light / System / Dark — System destacado
    3. Card "Accent Colour" com três swatches — Blue selecionado
    4. Card "Colour Tokens" com 8 chips coloridos
    5. Card "ThemeChangeEvent" com "Last event: none yet"
    6. Clique **Dark** → toda a UI alterna para a paleta escura com transição suave
    7. Clique **Light** → volta para a paleta clara
    8. Clique swatch **Violet** → badge e destaque mudam para violeta
    9. Ative o switch "Simulate OS dark mode" → com modo System, a UI fica escura
    10. Clique **Fire dark event** → "Last event:" mostra `ThemeChangeEvent(mode=<ThemeMode.DARK: 'dark'>)`

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos passam em verde. O exemplo foi escrito para ser `mypy --strict` clean —
toda variável e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização de tema

```
Clique em "Dark"
      │
      ▼
set_dark() → _apply_mode(ThemeMode.DARK)
      │
      ├─ app.set_state(...)   → atualiza forced_mode no estado
      │
      └─ app.set_theme(...)   → propaga Theme novo para o reconciliador
                                      │
                                      ▼
                              view(app) chamada novamente
                                      │
                                      ▼
                              _is_dark(app) retorna True
                                      │
                                      ▼
                              todos os containers leem _DARK_*
                                      │
                                      ▼
                              reconciliador calcula patches Update
                              (só os Style que mudaram)
                                      │
                                      ▼
                              DOM atualizado com transição de 200 ms
```

### Por que `set_state` e `set_theme` são chamados juntos?

`app.set_state` atualiza o **seu** estado local (`forced_mode`) para que os
botões reflitam qual está ativo. `app.set_theme` atualiza o `Theme` do framework
para que `app.theme.is_dark()` e `app.theme.primary` retornem os valores certos
na próxima chamada de `view`. São responsabilidades separadas — omitir qualquer
um deles deixaria parte da UI dessincronizada.

### `ThemeMode.SYSTEM` e `app.media`

Quando o modo é `SYSTEM`, `Theme.is_dark` consulta
`platform_dark_mode=app.media.platform_dark_mode`. O campo `app.media` é um
`MediaQueryData` que o host atualiza automaticamente quando o SO muda de esquema.
O switch no card "Colour Mode" simula essa atualização chamando `_update_media`
diretamente — em produção você nunca precisa fazer isso; o host cuida disso.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Usar `App.set_theme` para trocar o tema e acionar um rebuild coalesced
- ✅ Resolver `ThemeMode.SYSTEM` com `Theme.is_dark(platform_dark_mode=...)`
- ✅ Construir paletas de cor semânticas para ambos os esquemas como constantes
- ✅ Usar `Transition` para animar mudanças de cor suavemente
- ✅ Reagir a `ThemeChangeEvent` (notificação do SO) com um handler tipado
- ✅ Criar factories de handler (`_make_swatch_handler`) para closures corretos em loops
- ✅ Combinar `set_state` + `set_theme` para manter estado local e tema sincronizados

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Salve o modo escolhido no `localStorage` do browser (Modo A) ou em uma
  sessão de servidor (Modo B) para que persista entre reloads
- 💡 Adicione um quarto swatch com cores personalizadas via `Color(r=..., g=..., b=...)`
- 💡 Explore o exemplo [Settings Panel](./settings-panel.md) para ver como persistir
  preferências do usuário
- 💡 Leia [Modos de execução](../tutorial/modes.md) para entender como o mesmo
  `app.py` funciona nos dois transports sem nenhuma mudança
