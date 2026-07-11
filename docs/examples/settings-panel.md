# Settings Panel — Controles de Seleção em Ação 🚀

Construa um painel de configurações completo com **Switch**, **Checkbox**, **Slider**, **RadioGroup** e **SegmentedControl** — e veja como vincular todos eles a um único dataclass de estado de forma limpa e tipada.

---

## O que você vai construir

Um painel de configurações dividido em quatro seções, mais um cartão de resumo ao vivo:

| Seção | Widgets | O que controla |
|---|---|---|
| **Notifications** | Switch + Checkbox | Notificações push, alertas por e-mail, sons |
| **Appearance** | SegmentedControl + Slider | Tema (System/Light/Dark), tamanho de fonte, qualidade |
| **Audio & Storage** | Slider + Switch | Volume de reprodução, auto-save de rascunhos |
| **Language** | RadioGroup | Idioma da interface |
| **Live summary** | Card (apenas leitura) | Reflexo em tempo real de todos os valores acima |

Cada interação — mover um slider, marcar uma caixa, escolher um segmento — **atualiza imediatamente** o cartão de resumo, tornando a vinculação bidirecional visível de forma concreta.

!!! note "Nota — por que um resumo ao vivo?"
    O cartão de resumo não é decoração. Ele prova que cada controle realmente modifica o estado compartilhado. Se você clicar num controle e o resumo não mudar, há um bug. É o teste de fumaça mais rápido que existe.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada antes de continuar:

- [Tutorial básico](../tutorial/index.md) — `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como o ciclo de atualização funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

```bash
mkdir -p examples/settings-panel
touch examples/settings-panel/app.py
```

---

## Passo 1 — Definindo as constantes de opções

Antes do estado, defina as listas de opções para os controles de seleção. Mantê-las como constantes no topo do arquivo evita duplicação e facilita ajustes futuros.

```python
from __future__ import annotations

_THEME_OPTIONS: list[str] = ["System", "Light", "Dark"]
_LANGUAGE_OPTIONS: list[str] = ["English", "Português", "Español", "Français"]
_QUALITY_OPTIONS: list[str] = ["Low", "Medium", "High", "Ultra"]
```

!!! tip "Dica — índice como estado, não a string"
    O estado guarda o **índice** (`theme_index: int = 0`), não a string `"System"`. Isso torna o estado serializado compacto e independente de tradução. Para exibir o rótulo, use `_THEME_OPTIONS[state.theme_index]` na hora do render.

---

## Passo 2 — Modelando o estado

Com as opções definidas, modele exatamente o que precisa persistir entre renders:

```python
from dataclasses import dataclass


@dataclass
class SettingsState:
    """All mutable settings controlled by the panel.

    Attributes:
        notifications_enabled: Master switch for push notifications.
        email_alerts: Whether to send e-mail alerts on events.
        sound_enabled: Whether in-app sounds are active.
        auto_save: Whether drafts are saved automatically.
        theme_index: Index into ``_THEME_OPTIONS`` (0=System, 1=Light, 2=Dark).
        language_index: Index into ``_LANGUAGE_OPTIONS``.
        volume: Playback volume in ``[0, 100]``.
        font_size: Preferred font size in ``[10, 30]`` logical points.
        quality_index: Index into ``_QUALITY_OPTIONS`` (stream/render quality).
    """

    notifications_enabled: bool = True
    email_alerts: bool = False
    sound_enabled: bool = True
    auto_save: bool = True
    theme_index: int = 0
    language_index: int = 0
    volume: float = 70.0
    font_size: float = 16.0
    quality_index: int = 2


def make_state() -> SettingsState:
    """Build the initial settings state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults.
    """
    return SettingsState()
```

Observe que `make_state` é a função que o tempestweb chama para inicializar o app. Ela precisa existir com esse nome exato no módulo.

---

## Passo 3 — Os tipos de evento

Dois tipos de evento chegam dos controles de entrada. Importe-os de `tempest_core.widgets.events`:

```python
from tempest_core.widgets.events import SlideEvent, ToggleEvent
```

| Tipo | Usado por | Campo relevante |
|---|---|---|
| `ToggleEvent` | `Switch`, `Checkbox` | `.checked: bool` |
| `SlideEvent` | `Slider` | `.value: float` |

`RadioGroup` e `SegmentedControl` entregam diretamente o índice (`int`) ao callback — sem wrapper de evento.

---

## Passo 4 — Seção Notifications

A primeira seção usa `Switch` para o controle mestre e dois `Checkbox` para sub-opções. Organizamos a UI em uma função `_notifications_card` que recebe o `app` e retorna um `Card`:

```python
from tempest_core import App, Style, Widget
from tempest_core.components import AppBar, Card, Divider, Scaffold
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import Checkbox, Column, Row, Switch, Text
from tempest_core.widgets.events import ToggleEvent


def _notifications_card(app: App[SettingsState]) -> Widget:
    """Render the Notifications section with Switch and Checkbox controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the notification preference controls.
    """
    state: SettingsState = app.state

    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle master notification switch."""
        app.set_state(lambda s: setattr(s, "notifications_enabled", event.checked))

    def on_email_toggle(event: ToggleEvent) -> None:
        """Toggle e-mail alert preference."""
        app.set_state(lambda s: setattr(s, "email_alerts", event.checked))

    def on_sound_toggle(event: ToggleEvent) -> None:
        """Toggle in-app sound preference."""
        app.set_state(lambda s: setattr(s, "sound_enabled", event.checked))

    return Card(
        key="notifications-card",
        children=[
            Text(
                content="Notifications",
                key="notif-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="notif-divider"),
            Row(
                key="notif-master-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Enable notifications",
                        key="notif-master-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.notifications_enabled,
                        on_change=on_notifications_toggle,
                        key="notif-switch",
                    ),
                ],
            ),
            Checkbox(
                label="Send e-mail alerts",
                checked=state.email_alerts,
                on_change=on_email_toggle,
                key="email-checkbox",
            ),
            Checkbox(
                label="Play sounds",
                checked=state.sound_enabled,
                on_change=on_sound_toggle,
                key="sound-checkbox",
            ),
        ],
    )
```

!!! info "Nota — `Switch` num `Row` com `grow=1.0`"
    O `Text` com `grow=1.0` ocupa todo o espaço disponível na linha, empurrando o `Switch` para a direita — o padrão clássico de linha de configuração em iOS e Android. O `gap=12.0` no `Row` adiciona o espaçamento horizontal entre os dois.

---

## Passo 5 — Seção Appearance

Esta seção introduz `SegmentedControl` (para tema e qualidade) e `Slider` (para tamanho de fonte):

```python
from tempest_core.components import SegmentedControl
from tempest_core.widgets import Slider
from tempest_core.widgets.events import SlideEvent


def _appearance_card(app: App[SettingsState]) -> Widget:
    """Render the Appearance section with SegmentedControl and Slider controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the theme, font-size and quality controls.
    """
    state: SettingsState = app.state

    def on_theme_select(index: int) -> None:
        """Select a colour theme."""
        app.set_state(lambda s: setattr(s, "theme_index", index))

    def on_quality_select(index: int) -> None:
        """Select the render/stream quality level."""
        app.set_state(lambda s: setattr(s, "quality_index", index))

    def on_font_size_change(event: SlideEvent) -> None:
        """Adjust the preferred font size."""
        app.set_state(lambda s: setattr(s, "font_size", round(event.value, 1)))

    return Card(
        key="appearance-card",
        children=[
            Text(
                content="Appearance",
                key="appearance-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="appearance-divider"),
            Text(
                content="Theme",
                key="theme-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_THEME_OPTIONS,
                selected=state.theme_index,
                on_select=on_theme_select,
                key="theme-segments",
            ),
            Text(
                content=f"Font size: {state.font_size:.0f} pt",
                key="font-size-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.font_size,
                min_value=10.0,
                max_value=30.0,
                step=1.0,
                on_change=on_font_size_change,
                key="font-slider",
            ),
            Text(
                content="Render quality",
                key="quality-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_QUALITY_OPTIONS,
                selected=state.quality_index,
                on_select=on_quality_select,
                key="quality-segments",
            ),
        ],
    )
```

!!! tip "Dica — label dinâmico acima do Slider"
    O `Text` antes do `Slider` usa `f"Font size: {state.font_size:.0f} pt"`. A cada movimento do slider o estado muda → `view` é chamada novamente → o label atualiza. Não há nenhuma variável local ou `ref` manual: o estado *é* a fonte da verdade.

---

## Passo 6 — Seção Audio & Storage

Volume com `Slider` e auto-save com `Switch`, seguindo os mesmos padrões:

```python
def _audio_card(app: App[SettingsState]) -> Widget:
    """Render the Audio section with a volume Slider and auto-save Switch.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the audio and save controls.
    """
    state: SettingsState = app.state

    def on_volume_change(event: SlideEvent) -> None:
        """Adjust playback volume."""
        app.set_state(lambda s: setattr(s, "volume", round(event.value)))

    def on_auto_save_toggle(event: ToggleEvent) -> None:
        """Toggle auto-save preference."""
        app.set_state(lambda s: setattr(s, "auto_save", event.checked))

    return Card(
        key="audio-card",
        children=[
            Text(
                content="Audio & Storage",
                key="audio-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="audio-divider"),
            Text(
                content=f"Volume: {state.volume:.0f}%",
                key="volume-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.volume,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                on_change=on_volume_change,
                key="volume-slider",
            ),
            Row(
                key="auto-save-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Auto-save drafts",
                        key="auto-save-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.auto_save,
                        on_change=on_auto_save_toggle,
                        key="auto-save-switch",
                    ),
                ],
            ),
        ],
    )
```

---

## Passo 7 — Seção Language

`RadioGroup` é a escolha certa para seleção única com todos os itens visíveis simultaneamente:

```python
from tempest_core.components import RadioGroup


def _language_card(app: App[SettingsState]) -> Widget:
    """Render the Language section with a RadioGroup control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the language radio group.
    """
    state: SettingsState = app.state

    def on_language_select(index: int) -> None:
        """Select the preferred interface language."""
        app.set_state(lambda s: setattr(s, "language_index", index))

    return Card(
        key="language-card",
        children=[
            Text(
                content="Language",
                key="language-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="language-divider"),
            RadioGroup(
                options=_LANGUAGE_OPTIONS,
                selected=state.language_index,
                on_select=on_language_select,
                key="language-radio",
            ),
        ],
    )
```

!!! info "Nota — `RadioGroup` vs. `SegmentedControl`"
    Use `RadioGroup` quando houver mais de 3-4 opções ou quando os rótulos forem longos — ele empilha as opções verticalmente. Use `SegmentedControl` para 2-4 opções curtas que cabem numa linha horizontal.

---

## Passo 8 — O cartão de resumo ao vivo

Esta função recebe diretamente o `state` (sem o `app` inteiro), pois não precisa registrar handlers — é somente leitura:

```python
def _summary_card(state: SettingsState) -> Widget:
    """Render a live summary of all current settings.

    This card re-renders on every state change and shows all selected values
    so the user can verify that every control is truly bound to the state.

    Args:
        state: The current snapshot of :class:`SettingsState`.

    Returns:
        A ``Card`` listing all current setting values.
    """
    theme_name: str = _THEME_OPTIONS[state.theme_index]
    language_name: str = _LANGUAGE_OPTIONS[state.language_index]
    quality_name: str = _QUALITY_OPTIONS[state.quality_index]
    notif_text: str = "on" if state.notifications_enabled else "off"
    email_text: str = "yes" if state.email_alerts else "no"
    sound_text: str = "on" if state.sound_enabled else "off"
    save_text: str = "on" if state.auto_save else "off"

    lines: list[Widget] = [
        Text(
            content="Live summary",
            key="summary-heading",
            style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="summary-divider"),
        Text(
            content=f"Notifications: {notif_text}  |  E-mail alerts: {email_text}",
            key="summary-notif",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Sound: {sound_text}  |  Auto-save: {save_text}",
            key="summary-sound",
            style=Style(font_size=13.0),
        ),
        Text(
            content=(
                f"Theme: {theme_name}  |  Font: {state.font_size:.0f} pt"
                f"  |  Quality: {quality_name}"
            ),
            key="summary-appearance",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Volume: {state.volume:.0f}%  |  Language: {language_name}",
            key="summary-audio",
            style=Style(font_size=13.0),
        ),
    ]

    return Card(key="summary-card", children=lines)
```

---

## Passo 9 — Montando tudo em `view`

A função `view` é o ponto de entrada do tempestweb. Ela chama cada builder de seção e os organiza num `Scaffold` com `AppBar`:

```python
def view(app: App[SettingsState]) -> Widget:
    """Render the full settings panel from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    return Scaffold(
        key="settings-scaffold",
        app_bar=AppBar(title="Settings", key="settings-appbar"),
        body=Column(
            key="settings-body",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _notifications_card(app),
                _appearance_card(app),
                _audio_card(app),
                _language_card(app),
                _summary_card(app.state),
            ],
        ),
    )
```

!!! tip "Dica — `_summary_card(app.state)` vs. `_summary_card(app)`"
    Passar `app.state` (em vez de `app`) ao cartão de resumo comunica claramente que ele é **somente leitura**. Quem lê o código sabe imediatamente que essa função não registra handlers. É uma convenção de design, não uma restrição técnica.

---

## O app completo ✅

Aqui está o arquivo `examples/settings-panel/app.py` completo, pronto para copiar:

```python
"""Settings panel — demonstrates selection controls bound to a settings dataclass.

Every control (Switch, Checkbox, Slider, RadioGroup, SegmentedControl) is wired
to a dedicated field in :class:`SettingsState`.  Any change immediately re-renders
a live summary card at the bottom that reflects the current state — so the demo
makes the two-way binding visible.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AppBar,
    Card,
    Divider,
    RadioGroup,
    Scaffold,
    SegmentedControl,
)
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import (
    Checkbox,
    Column,
    Row,
    Slider,
    Switch,
    Text,
)
from tempest_core.widgets.events import SlideEvent, ToggleEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_THEME_OPTIONS: list[str] = ["System", "Light", "Dark"]
_LANGUAGE_OPTIONS: list[str] = ["English", "Português", "Español", "Français"]
_QUALITY_OPTIONS: list[str] = ["Low", "Medium", "High", "Ultra"]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SettingsState:
    """All mutable settings controlled by the panel.

    Attributes:
        notifications_enabled: Master switch for push notifications.
        email_alerts: Whether to send e-mail alerts on events.
        sound_enabled: Whether in-app sounds are active.
        auto_save: Whether drafts are saved automatically.
        theme_index: Index into ``_THEME_OPTIONS`` (0=System, 1=Light, 2=Dark).
        language_index: Index into ``_LANGUAGE_OPTIONS``.
        volume: Playback volume in ``[0, 100]``.
        font_size: Preferred font size in ``[10, 30]`` logical points.
        quality_index: Index into ``_QUALITY_OPTIONS`` (stream/render quality).
    """

    notifications_enabled: bool = True
    email_alerts: bool = False
    sound_enabled: bool = True
    auto_save: bool = True
    theme_index: int = 0
    language_index: int = 0
    volume: float = 70.0
    font_size: float = 16.0
    quality_index: int = 2


def make_state() -> SettingsState:
    """Build the initial settings state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults.
    """
    return SettingsState()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _notifications_card(app: App[SettingsState]) -> Widget:
    """Render the Notifications section with Switch and Checkbox controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the notification preference controls.
    """
    state: SettingsState = app.state

    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle master notification switch."""
        app.set_state(lambda s: setattr(s, "notifications_enabled", event.checked))

    def on_email_toggle(event: ToggleEvent) -> None:
        """Toggle e-mail alert preference."""
        app.set_state(lambda s: setattr(s, "email_alerts", event.checked))

    def on_sound_toggle(event: ToggleEvent) -> None:
        """Toggle in-app sound preference."""
        app.set_state(lambda s: setattr(s, "sound_enabled", event.checked))

    return Card(
        key="notifications-card",
        children=[
            Text(
                content="Notifications",
                key="notif-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="notif-divider"),
            Row(
                key="notif-master-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Enable notifications",
                        key="notif-master-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.notifications_enabled,
                        on_change=on_notifications_toggle,
                        key="notif-switch",
                    ),
                ],
            ),
            Checkbox(
                label="Send e-mail alerts",
                checked=state.email_alerts,
                on_change=on_email_toggle,
                key="email-checkbox",
            ),
            Checkbox(
                label="Play sounds",
                checked=state.sound_enabled,
                on_change=on_sound_toggle,
                key="sound-checkbox",
            ),
        ],
    )


def _appearance_card(app: App[SettingsState]) -> Widget:
    """Render the Appearance section with SegmentedControl and Slider controls.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the theme, font-size and quality controls.
    """
    state: SettingsState = app.state

    def on_theme_select(index: int) -> None:
        """Select a colour theme."""
        app.set_state(lambda s: setattr(s, "theme_index", index))

    def on_quality_select(index: int) -> None:
        """Select the render/stream quality level."""
        app.set_state(lambda s: setattr(s, "quality_index", index))

    def on_font_size_change(event: SlideEvent) -> None:
        """Adjust the preferred font size."""
        app.set_state(lambda s: setattr(s, "font_size", round(event.value, 1)))

    return Card(
        key="appearance-card",
        children=[
            Text(
                content="Appearance",
                key="appearance-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="appearance-divider"),
            Text(
                content="Theme",
                key="theme-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_THEME_OPTIONS,
                selected=state.theme_index,
                on_select=on_theme_select,
                key="theme-segments",
            ),
            Text(
                content=f"Font size: {state.font_size:.0f} pt",
                key="font-size-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.font_size,
                min_value=10.0,
                max_value=30.0,
                step=1.0,
                on_change=on_font_size_change,
                key="font-slider",
            ),
            Text(
                content="Render quality",
                key="quality-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            SegmentedControl(
                options=_QUALITY_OPTIONS,
                selected=state.quality_index,
                on_select=on_quality_select,
                key="quality-segments",
            ),
        ],
    )


def _audio_card(app: App[SettingsState]) -> Widget:
    """Render the Audio section with a volume Slider and auto-save Switch.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the audio and save controls.
    """
    state: SettingsState = app.state

    def on_volume_change(event: SlideEvent) -> None:
        """Adjust playback volume."""
        app.set_state(lambda s: setattr(s, "volume", round(event.value)))

    def on_auto_save_toggle(event: ToggleEvent) -> None:
        """Toggle auto-save preference."""
        app.set_state(lambda s: setattr(s, "auto_save", event.checked))

    return Card(
        key="audio-card",
        children=[
            Text(
                content="Audio & Storage",
                key="audio-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="audio-divider"),
            Text(
                content=f"Volume: {state.volume:.0f}%",
                key="volume-label",
                style=Style(font_size=13.0, font_weight=FontWeight.BOLD),
            ),
            Slider(
                value=state.volume,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                on_change=on_volume_change,
                key="volume-slider",
            ),
            Row(
                key="auto-save-row",
                style=Style(gap=12.0, align=AlignItems.CENTER),
                children=[
                    Text(
                        content="Auto-save drafts",
                        key="auto-save-label",
                        style=Style(font_size=14.0, grow=1.0),
                    ),
                    Switch(
                        checked=state.auto_save,
                        on_change=on_auto_save_toggle,
                        key="auto-save-switch",
                    ),
                ],
            ),
        ],
    )


def _language_card(app: App[SettingsState]) -> Widget:
    """Render the Language section with a RadioGroup control.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A ``Card`` containing the language radio group.
    """
    state: SettingsState = app.state

    def on_language_select(index: int) -> None:
        """Select the preferred interface language."""
        app.set_state(lambda s: setattr(s, "language_index", index))

    return Card(
        key="language-card",
        children=[
            Text(
                content="Language",
                key="language-heading",
                style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="language-divider"),
            RadioGroup(
                options=_LANGUAGE_OPTIONS,
                selected=state.language_index,
                on_select=on_language_select,
                key="language-radio",
            ),
        ],
    )


def _summary_card(state: SettingsState) -> Widget:
    """Render a live summary of all current settings.

    Args:
        state: The current snapshot of :class:`SettingsState`.

    Returns:
        A ``Card`` listing all current setting values.
    """
    theme_name: str = _THEME_OPTIONS[state.theme_index]
    language_name: str = _LANGUAGE_OPTIONS[state.language_index]
    quality_name: str = _QUALITY_OPTIONS[state.quality_index]
    notif_text: str = "on" if state.notifications_enabled else "off"
    email_text: str = "yes" if state.email_alerts else "no"
    sound_text: str = "on" if state.sound_enabled else "off"
    save_text: str = "on" if state.auto_save else "off"

    lines: list[Widget] = [
        Text(
            content="Live summary",
            key="summary-heading",
            style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="summary-divider"),
        Text(
            content=f"Notifications: {notif_text}  |  E-mail alerts: {email_text}",
            key="summary-notif",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Sound: {sound_text}  |  Auto-save: {save_text}",
            key="summary-sound",
            style=Style(font_size=13.0),
        ),
        Text(
            content=(
                f"Theme: {theme_name}  |  Font: {state.font_size:.0f} pt"
                f"  |  Quality: {quality_name}"
            ),
            key="summary-appearance",
            style=Style(font_size=13.0),
        ),
        Text(
            content=f"Volume: {state.volume:.0f}%  |  Language: {language_name}",
            key="summary-audio",
            style=Style(font_size=13.0),
        ),
    ]

    return Card(key="summary-card", children=lines)


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[SettingsState]) -> Widget:
    """Render the full settings panel from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    return Scaffold(
        key="settings-scaffold",
        app_bar=AppBar(title="Settings", key="settings-appbar"),
        body=Column(
            key="settings-body",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=[
                _notifications_card(app),
                _appearance_card(app),
                _audio_card(app),
                _language_card(app),
                _summary_card(app.state),
            ],
        ),
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/settings-panel
```

O Python roda **dentro do browser** via Pyodide. Nenhum servidor necessário — abra o URL impresso no terminal.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/settings-panel
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e atualiza o DOM.

!!! check "Verificação"
    Em qualquer modo, confirme que:

    1. `AppBar` exibe o título **Settings** no topo
    2. Quatro cartões aparecem: Notifications, Appearance, Audio & Storage, Language
    3. Desligar o `Switch` master de Notifications atualiza o campo `notifications` no cartão de resumo
    4. Mover o slider de volume muda o label **"Volume: XX%"** acima dele e o campo correspondente no resumo
    5. Clicar num segmento do `SegmentedControl` de tema muda o campo `Theme` no resumo
    6. Selecionar um idioma no `RadioGroup` muda o campo `Language` no resumo

---

## Verificação automatizada ✅

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

Todos os quatro devem passar em verde. O exemplo foi escrito para ser `mypy --strict` clean — toda variável, parâmetro e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização

```
Usuário interage com um controle
          │
          ▼
handler (ex: on_volume_change)
          │
          ▼
app.set_state(mutador lambda)
          │
          ▼
tempestweb aplica o mutador → estado novo
          │
          ▼
view(app) chamada novamente → nova árvore de widgets
          │
          ▼
reconciliador calcula diff (patches mínimos)
          │
          ▼
DOM atualizado — só o que mudou
```

### Por que dividir em builders de seção?

`view` poderia construir tudo inline, mas ficaria com mais de 200 linhas. Dividir em `_notifications_card`, `_appearance_card` etc. traz dois benefícios:

1. **Leitura:** cada função cabe numa tela — propósito imediato, sem scroll.
2. **Testabilidade:** cada builder recebe `App[SettingsState]` e retorna `Widget` — é possível testá-los isoladamente injetando um `app` com estado fixo.

### Estado como índice, não como string

Guardar `theme_index: int` em vez de `theme: str` tem uma consequência importante: o mesmo estado serializado funciona com listas de opções em qualquer idioma. Se você quiser localizar os rótulos dos temas, basta trocar `_THEME_OPTIONS` — o estado não muda.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar **múltiplos tipos de controle** (bool, int, float) em um único dataclass tipado
- ✅ Usar `Switch` e `Checkbox` com `ToggleEvent.checked`
- ✅ Usar `Slider` com `SlideEvent.value` e arredondamento explícito
- ✅ Usar `SegmentedControl` e `RadioGroup` com índice inteiro como estado
- ✅ Organizar a UI em **builders de seção** independentes e testáveis
- ✅ Construir um **cartão de resumo ao vivo** como prova de vinculação bidirecional
- ✅ Usar `Scaffold` + `AppBar` como estrutura de página padrão

---

## Próximos passos

- 💡 Explore [Tabs Profile](./tabs-profile.md) para ver `Switch` e `Checkbox` dentro de um painel com abas
- 💡 Veja [Stopwatch](./stopwatch.md) para aprender a gerenciar estado temporal com `asyncio`
- 💡 Leia [Gerenciando estado](../tutorial/state.md) para um tratamento completo do ciclo `set_state`
- 💡 Adicione persistência: serialize `SettingsState` para `localStorage` no Modo A via `pyodide.ffi` ou para um endpoint REST no Modo B
