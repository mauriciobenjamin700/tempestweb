# Tabbed settings — seleção controlada por estado 🚀

Neste exemplo você vai construir um **painel de configurações com abas**, usando
os componentes de seleção do core: `Tabs`, `SegmentedControl`, `RadioGroup` e
`Chip` — todos controlados por índices inteiros no estado e handlers `on_select`.

---

## O que você vai construir

- 🗂️ Um **Tabs** alternando entre "Appearance" e "Notifications".
- 🎚️ Um **SegmentedControl** para escolher o tema (Light / Dark / Auto).
- 🔘 Um **RadioGroup** para a frequência de notificações.
- 🏷️ Um **Chip** que reflete a escolha atual.

---

## Pré-requisitos

```bash
pip install tempestweb
```

!!! tip "Dica"
    Se você ainda não conhece o ciclo estado → view → patches, leia o
    [tutorial de introdução](../tutorial/index.md).

---

## Passo 1 — As opções e o estado

As opções são constantes de módulo; o estado guarda apenas **índices inteiros**
apontando para a escolha ativa de cada controle.

```python
from __future__ import annotations

from dataclasses import dataclass

TAB_LABELS: list[str] = ["Appearance", "Notifications"]
THEME_OPTIONS: list[str] = ["Light", "Dark", "Auto"]
FREQUENCY_OPTIONS: list[str] = ["Off", "Daily", "Weekly", "Realtime"]


@dataclass
class SettingsState:
    """State for the tabbed settings panel.

    Attributes:
        active_tab: Index into :data:`TAB_LABELS` of the open tab.
        theme: Index into :data:`THEME_OPTIONS` of the chosen theme.
        frequency: Index into :data:`FREQUENCY_OPTIONS` of the chosen cadence.
    """

    active_tab: int = 0
    theme: int = 2
    frequency: int = 1


def make_state() -> SettingsState:
    """Build the initial state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults selected.
    """
    return SettingsState()
```

!!! note "Nota — índices, não strings"
    Guardar `theme: int = 2` (em vez de `"Auto"`) mantém o estado pequeno e
    desacoplado dos rótulos. `SegmentedControl`, `RadioGroup` e `Tabs` todos
    falam em índices via `selected`/`active` e `on_select`.

---

## Passo 2 — Os handlers

Cada controle de seleção entrega o índice escolhido a um handler dedicado:

```python
def select_tab(index: int) -> None:
    """Switch the active tab."""
    app.set_state(lambda s: setattr(s, "active_tab", index))

def select_theme(index: int) -> None:
    """Pick a theme from the segmented control."""
    app.set_state(lambda s: setattr(s, "theme", index))

def select_frequency(index: int) -> None:
    """Pick a notification cadence from the radio group."""
    app.set_state(lambda s: setattr(s, "frequency", index))
```

---

## Passo 3 — O painel condicional

Dependendo da aba ativa, montamos um `Card` diferente. Repare como cada controle
recebe `selected` (o índice atual) + `on_select` (o handler), e o `Chip` reflete a
escolha com `selected=True`.

```python
from tempest_core import Row, Style, Text
from tempestweb.components import Card, Chip, RadioGroup, SegmentedControl

if state.active_tab == 0:
    panel: Widget = Card(
        key="appearance-card",
        children=[
            Text(content="Theme", key="theme-title"),
            SegmentedControl(
                key="theme-segmented",
                options=THEME_OPTIONS,
                selected=state.theme,
                on_select=select_theme,
            ),
            Row(
                style=Style(gap=4.0),
                children=[
                    Chip(
                        key="theme-chip",
                        label=f"Theme: {THEME_OPTIONS[state.theme]}",
                        selected=True,
                    ),
                ],
            ),
        ],
    )
else:
    panel = Card(
        key="notifications-card",
        children=[
            Text(content="Notification frequency", key="frequency-title"),
            RadioGroup(
                key="frequency-radio",
                options=FREQUENCY_OPTIONS,
                selected=state.frequency,
                on_select=select_frequency,
            ),
            Row(
                style=Style(gap=4.0),
                children=[
                    Chip(
                        key="frequency-chip",
                        label=f"Notify: {FREQUENCY_OPTIONS[state.frequency]}",
                        selected=True,
                    ),
                ],
            ),
        ],
    )
```

---

## Passo 4 — A árvore raiz

O `Tabs` fica no topo (`active` + `on_select`), seguido pelo painel da aba ativa.

```python
from tempest_core import Column, Style, Text
from tempest_core.style import Edge
from tempestweb.components import Tabs

return Column(
    style=Style(gap=12.0, padding=Edge.all(16)),
    children=[
        Text(content="Settings", key="heading"),
        Tabs(
            key="settings-tabs",
            tabs=TAB_LABELS,
            active=state.active_tab,
            on_select=select_tab,
        ),
        panel,
    ],
)
```

---

## O app completo

```python
"""Tabbed settings — a tempestweb example for the core's selection components.

This ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

It showcases the core's selection and navigation widgets — :class:`Tabs`,
:class:`SegmentedControl`, :class:`RadioGroup`, :class:`Chip` and :class:`Card` —
wired so that every selection is fully state-driven through ``on_select`` /
``on_click`` handlers. The application never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import Card, Chip, RadioGroup, SegmentedControl, Tabs

TAB_LABELS: list[str] = ["Appearance", "Notifications"]
THEME_OPTIONS: list[str] = ["Light", "Dark", "Auto"]
FREQUENCY_OPTIONS: list[str] = ["Off", "Daily", "Weekly", "Realtime"]


@dataclass
class SettingsState:
    """State for the tabbed settings panel.

    Attributes:
        active_tab: Index into :data:`TAB_LABELS` of the open tab.
        theme: Index into :data:`THEME_OPTIONS` of the chosen theme.
        frequency: Index into :data:`FREQUENCY_OPTIONS` of the chosen cadence.
    """

    active_tab: int = 0
    theme: int = 2
    frequency: int = 1


def make_state() -> SettingsState:
    """Build the initial state.

    Returns:
        A fresh :class:`SettingsState` with sensible defaults selected.
    """
    return SettingsState()


def view(app: App[SettingsState]) -> Widget:
    """Render the settings UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def select_tab(index: int) -> None:
        """Switch the active tab.

        Args:
            index: Index of the tab to activate.
        """
        app.set_state(lambda s: setattr(s, "active_tab", index))

    def select_theme(index: int) -> None:
        """Pick a theme from the segmented control.

        Args:
            index: Index into :data:`THEME_OPTIONS`.
        """
        app.set_state(lambda s: setattr(s, "theme", index))

    def select_frequency(index: int) -> None:
        """Pick a notification cadence from the radio group.

        Args:
            index: Index into :data:`FREQUENCY_OPTIONS`.
        """
        app.set_state(lambda s: setattr(s, "frequency", index))

    state = app.state

    if state.active_tab == 0:
        panel: Widget = Card(
            key="appearance-card",
            children=[
                Text(content="Theme", key="theme-title"),
                SegmentedControl(
                    key="theme-segmented",
                    options=THEME_OPTIONS,
                    selected=state.theme,
                    on_select=select_theme,
                ),
                Row(
                    style=Style(gap=4.0),
                    children=[
                        Chip(
                            key="theme-chip",
                            label=f"Theme: {THEME_OPTIONS[state.theme]}",
                            selected=True,
                        ),
                    ],
                ),
            ],
        )
    else:
        panel = Card(
            key="notifications-card",
            children=[
                Text(content="Notification frequency", key="frequency-title"),
                RadioGroup(
                    key="frequency-radio",
                    options=FREQUENCY_OPTIONS,
                    selected=state.frequency,
                    on_select=select_frequency,
                ),
                Row(
                    style=Style(gap=4.0),
                    children=[
                        Chip(
                            key="frequency-chip",
                            label=f"Notify: {FREQUENCY_OPTIONS[state.frequency]}",
                            selected=True,
                        ),
                    ],
                ),
            ],
        )

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Settings", key="heading"),
            Tabs(
                key="settings-tabs",
                tabs=TAB_LABELS,
                active=state.active_tab,
                on_select=select_tab,
            ),
            panel,
        ],
    )
```

---

## Rodando o exemplo ▶

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/core-tabbed-settings
    ```

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/core-tabbed-settings
    ```

!!! check "Verificação"
    Na aba **Appearance**, clique em "Dark" no segmented control → o chip muda
    para "Theme: Dark". Clique na aba **Notifications** → aparece o radio group de
    frequência. ✅

---

## Recapitulando

- ✅ Guardar a seleção como **índices inteiros**, não strings.
- ✅ Usar `Tabs`, `SegmentedControl` e `RadioGroup` — todos com `on_select(index)`.
- ✅ Refletir a escolha em um `Chip` (`selected=True`).
- ✅ Renderizar um painel condicional conforme a aba ativa.
- ✅ Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Próximos passos"
    - Veja o [Painel de configurações](settings-panel.md) para mais controles.
    - Combine com [Alternador de tema](theme-switcher.md) para aplicar o tema de verdade.
