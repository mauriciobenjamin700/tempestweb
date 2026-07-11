# Perfil com Abas

> 🚀 **O que você vai construir:** uma tela de perfil com três seções — *Overview*, *Activity* e *Settings* — navegáveis por abas, com interruptores (Switch) que alteram preferências em tempo real.

---

## Por que esse exemplo importa?

Toda aplicação real precisa organizar conteúdo em seções sem sobrecarregar o usuário.
O `TabView` resolve exatamente isso: apresenta um conjunto de rótulos na parte superior e
troca o corpo da tela conforme a aba selecionada.

Neste tutorial você vai aprender a:

- Usar `TabView` para navegação entre seções;
- Responder ao `RouteChangeEvent` para atualizar o índice de aba no estado;
- Usar `Switch` com `ToggleEvent` para controles booleanos (notificações, modo escuro);
- Compor layouts ricos com `Card`, `Avatar`, `ListTile` e `Divider`.

!!! note "Nota"
    Este exemplo roda **sem nenhuma alteração** nos dois modos — WASM (Pyodide no
    browser) e Servidor (FastAPI + WebSocket). A mesma `view()` Python serve os dois.

---

## Pré-requisitos

Instale o tempestweb e confirme que o CLI está disponível:

```bash
pip install tempestweb
tempestweb --version
```

---

## Estrutura do projeto

```
examples/
└── tabs-profile/
    └── app.py
```

Crie a pasta e o arquivo:

```bash
mkdir -p examples/tabs-profile
touch examples/tabs-profile/app.py
```

---

## Passo 1 — Definir o estado

O estado guarda qual aba está ativa e as duas preferências booleanas (notificações e modo
escuro). Um segundo dataclass modela cada entrada da lista de atividades.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AppBar,
    Avatar,
    Card,
    Divider,
    ListTile,
    Scaffold,
)
from tempest_core.style import AlignItems, Edge, FontWeight
from tempest_core.widgets import (
    Column,
    Row,
    Switch,
    TabView,
    Text,
)
from tempest_core.widgets.events import RouteChangeEvent, ToggleEvent

_TABS: list[str] = ["Overview", "Activity", "Settings"]


@dataclass
class ActivityEntry:
    """A single item in the user's recent-activity feed.

    Attributes:
        title: Short description of the activity.
        subtitle: Timestamp or context string.
    """

    title: str
    subtitle: str


@dataclass
class ProfileState:
    """All mutable state for the tabbed-profile screen.

    Attributes:
        active_tab: Index of the currently visible tab (0 = Overview, etc.).
        notifications_on: Whether push notifications are enabled.
        dark_mode: Whether the user has chosen dark-mode.
        activity: Ordered list of recent activity entries.
    """

    active_tab: int = 0
    notifications_on: bool = True
    dark_mode: bool = True
    activity: list[ActivityEntry] = field(default_factory=list)


def make_state() -> ProfileState:
    """Build the initial profile state with seed activity entries.

    Returns:
        A fresh :class:`ProfileState` ready for the first render.
    """
    return ProfileState(
        activity=[
            ActivityEntry("Joined the platform", "2 years ago"),
            ActivityEntry("Completed onboarding", "2 years ago"),
            ActivityEntry("Published first project", "18 months ago"),
            ActivityEntry("Reached 100 followers", "1 year ago"),
            ActivityEntry("Earned contributor badge", "6 months ago"),
        ]
    )
```

!!! tip "Dica"
    `_TABS` é uma lista simples de strings. O `TabView` usa esses rótulos para
    renderizar os botões de aba — você não precisa de nenhuma configuração extra.

**O que acabou de acontecer:**

- `_TABS` define os três rótulos que o `TabView` vai exibir.
- `ProfileState.active_tab` é o único ponto de verdade sobre qual aba está visível.
- `make_state()` fornece dados iniciais de atividade para que a aba *Activity* já
  apareça populada desde o primeiro render.

---

## Passo 2 — Construir a seção Overview

A primeira aba exibe avatar, bio e estatísticas em cartões.

```python
def _overview_section(state: ProfileState) -> Widget:
    """Render the Overview tab: avatar, bio card, and stats row.

    Args:
        state: The current application state.

    Returns:
        A ``Column`` composing the overview content.
    """
    notifications_label = "on" if state.notifications_on else "off"
    dark_label = "dark" if state.dark_mode else "light"
    return Column(
        key="overview",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Row(
                key="profile-header",
                style=Style(gap=16.0, align=AlignItems.CENTER),
                children=[
                    Avatar(initials="AJ", size=72.0, key="avatar-lg"),
                    Column(
                        key="name-block",
                        style=Style(gap=4.0),
                        children=[
                            Text(
                                content="Alex Johnson",
                                key="full-name",
                                style=Style(
                                    font_size=22.0,
                                    font_weight=FontWeight.BOLD,
                                ),
                            ),
                            Text(
                                content="@alexj · Senior Engineer",
                                key="handle",
                                style=Style(font_size=14.0),
                            ),
                        ],
                    ),
                ],
            ),
            Card(
                key="bio-card",
                children=[
                    Text(
                        content="Bio",
                        key="bio-heading",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Text(
                        content=(
                            "Building developer tools and open-source libraries. "
                            "Passionate about clean architecture and great UX."
                        ),
                        key="bio-body",
                        style=Style(font_size=14.0),
                    ),
                ],
            ),
            Card(
                key="stats-card",
                children=[
                    Text(
                        content="Quick stats",
                        key="stats-heading",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Divider(key="stats-divider"),
                    Row(
                        key="stats-row",
                        style=Style(gap=24.0),
                        children=[
                            Column(
                                key="stat-projects",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="34",
                                        key="stat-projects-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Projects",
                                        key="stat-projects-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                            Column(
                                key="stat-followers",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="1.2k",
                                        key="stat-followers-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Followers",
                                        key="stat-followers-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                            Column(
                                key="stat-stars",
                                style=Style(gap=2.0, align=AlignItems.CENTER),
                                children=[
                                    Text(
                                        content="892",
                                        key="stat-stars-val",
                                        style=Style(
                                            font_size=20.0,
                                            font_weight=FontWeight.BOLD,
                                        ),
                                    ),
                                    Text(
                                        content="Stars",
                                        key="stat-stars-lbl",
                                        style=Style(font_size=12.0),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    Text(
                        content=(
                            f"Notifications: {notifications_label}"
                            f"  |  Theme: {dark_label}"
                        ),
                        key="prefs-summary",
                        style=Style(font_size=12.0),
                    ),
                ],
            ),
        ],
    )
```

!!! info "Info"
    O `Divider` dentro do cartão de estatísticas é um separador visual horizontal simples
    — nenhum parâmetro obrigatório além do `key`.

**Destaques:**

- `Avatar(initials="AJ", size=72.0)` — o componente pré-construído gera um círculo
  com as iniciais; não é preciso lidar com URLs de imagem.
- `Edge.all(16.0)` — aplica `padding` uniforme de 16 px em todos os lados.
- `AlignItems.CENTER` — alinha verticalmente o avatar e o bloco de nome.
- O resumo de preferências no rodapé (`prefs-summary`) já reflete o estado das
  configurações mesmo estando em outra aba — porque tudo compartilha o mesmo
  `ProfileState`.

---

## Passo 3 — Construir a seção Activity

A segunda aba itera sobre as entradas de atividade e cria um `ListTile` para cada uma,
separados por `Divider`.

```python
def _activity_section(state: ProfileState) -> Widget:
    """Render the Activity tab: a card list of recent events.

    Args:
        state: The current application state.

    Returns:
        A ``Column`` of activity list tiles inside a ``Card``.
    """
    tiles: list[Widget] = []
    for i, entry in enumerate(state.activity):
        tiles.append(
            ListTile(
                key=f"activity-{i}",
                leading=Avatar(initials=entry.title[0], size=36.0, key=f"av-{i}"),
                title=entry.title,
                subtitle=entry.subtitle,
            )
        )
        if i < len(state.activity) - 1:
            tiles.append(Divider(key=f"div-{i}"))
    return Column(
        key="activity",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content="Recent activity",
                key="activity-heading",
                style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
            ),
            Card(key="activity-card", children=tiles),
        ],
    )
```

!!! tip "Dica"
    Cada widget precisa de um `key` único dentro do mesmo pai. Aqui usamos
    `f"activity-{i}"` e `f"div-{i}"` para garantir isso em listas dinâmicas.
    O reconciliador usa essas chaves para aplicar patches mínimos no DOM.

**Destaques:**

- `ListTile` aceita `leading` (widget à esquerda), `title` e `subtitle`.
- O `if i < len(state.activity) - 1` evita um `Divider` após o último item.

---

## Passo 4 — Construir a seção Settings com Switch

A terceira aba usa `Switch` para controles booleanos. Cada `Switch` recebe um handler
de `ToggleEvent`.

```python
def _settings_section(
    state: ProfileState,
    on_notifications: RouteChangeEvent | None,
    toggle_notifications: ToggleEvent | None,
    toggle_dark: ToggleEvent | None,
    on_notifications_switch: object,
    on_dark_switch: object,
) -> Widget:
    """Render the Settings tab: notification and theme toggles inside cards.

    Args:
        state: The current application state.
        on_notifications: Unused placeholder kept for API symmetry.
        toggle_notifications: Unused placeholder kept for API symmetry.
        toggle_dark: Unused placeholder kept for API symmetry.
        on_notifications_switch: Zero-argument-accepting handler for the
            notifications ``Switch``.
        on_dark_switch: Zero-argument-accepting handler for the dark-mode
            ``Switch``.

    Returns:
        A ``Column`` of settings cards.
    """
    return Column(
        key="settings",
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content="Settings",
                key="settings-heading",
                style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
            ),
            Card(
                key="notif-card",
                children=[
                    ListTile(
                        key="notif-tile",
                        title="Push notifications",
                        subtitle="Receive alerts for mentions and replies",
                        trailing=Switch(
                            checked=state.notifications_on,
                            on_change=on_notifications_switch,  # type: ignore[arg-type]
                            key="notif-switch",
                        ),
                    ),
                ],
            ),
            Card(
                key="theme-card",
                children=[
                    ListTile(
                        key="theme-tile",
                        title="Dark mode",
                        subtitle="Use a dark colour palette",
                        trailing=Switch(
                            checked=state.dark_mode,
                            on_change=on_dark_switch,  # type: ignore[arg-type]
                            key="theme-switch",
                        ),
                    ),
                ],
            ),
            Card(
                key="account-card",
                children=[
                    Text(
                        content="Account",
                        key="account-heading",
                        style=Style(font_size=16.0, font_weight=FontWeight.BOLD),
                    ),
                    Divider(key="account-divider"),
                    ListTile(
                        key="email-tile",
                        leading=Avatar(initials="@", size=32.0, key="email-av"),
                        title="alex@example.com",
                        subtitle="Primary email address",
                    ),
                    ListTile(
                        key="joined-tile",
                        leading=Avatar(initials="J", size=32.0, key="joined-av"),
                        title="Joined",
                        subtitle="March 2022",
                    ),
                ],
            ),
        ],
    )
```

!!! info "Info"
    `ListTile` também aceita `trailing` — um widget colocado à direita. Aqui usamos
    o `Switch` nessa posição, um padrão clássico de tela de configurações.

---

## Passo 5 — A função `view` e os handlers de evento

Aqui tudo se conecta. A função `view` define os handlers de evento como funções
internas e decide qual seção renderizar com base em `state.active_tab`.

```python
def view(app: App[ProfileState]) -> Widget:
    """Render the tabbed-profile UI from the current state.

    The active section is determined by ``app.state.active_tab``.  Tapping a
    tab fires a :class:`~tempest_core.widgets.events.RouteChangeEvent`;
    the handler reads ``event.params["index"]`` and writes it back via
    :meth:`~tempest_core.core.state.App.set_state`.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """
    state: ProfileState = app.state

    # --- Tab-change handler -------------------------------------------------
    def on_tab_change(event: RouteChangeEvent) -> None:
        """Switch the active tab when the user taps a tab label.

        Args:
            event: The route-change event carrying the new tab index in
                ``params["index"]``.
        """
        index: int = int(event.params.get("index", 0))
        app.set_state(lambda s: setattr(s, "active_tab", index))

    # --- Toggle handlers (Settings tab) -------------------------------------
    def on_notifications_toggle(event: ToggleEvent) -> None:
        """Toggle push-notification preference.

        Args:
            event: The toggle event carrying the new ``checked`` state.
        """
        app.set_state(lambda s: setattr(s, "notifications_on", event.checked))

    def on_dark_toggle(event: ToggleEvent) -> None:
        """Toggle dark-mode preference.

        Args:
            event: The toggle event carrying the new ``checked`` state.
        """
        app.set_state(lambda s: setattr(s, "dark_mode", event.checked))

    # --- Build the active section -------------------------------------------
    tab: int = state.active_tab
    if tab == 0:
        body: Widget = _overview_section(state)
    elif tab == 1:
        body = _activity_section(state)
    else:
        body = _settings_section(
            state,
            on_notifications=None,
            toggle_notifications=None,
            toggle_dark=None,
            on_notifications_switch=on_notifications_toggle,
            on_dark_switch=on_dark_toggle,
        )

    return Scaffold(
        key="profile-scaffold",
        app_bar=AppBar(title="Profile", key="profile-appbar"),
        body=TabView(
            key="profile-tabs",
            tabs=_TABS,
            active=state.active_tab,
            on_change=on_tab_change,
            child=body,
        ),
    )
```

**O que está acontecendo:**

| Parte | Responsabilidade |
|---|---|
| `on_tab_change` | Lê `event.params["index"]` e grava em `active_tab` via `set_state` |
| `on_notifications_toggle` | Lê `event.checked` e inverte `notifications_on` |
| `on_dark_toggle` | Lê `event.checked` e inverte `dark_mode` |
| `if tab == 0 / 1 / else` | Seleciona qual builder de seção chamar |
| `TabView(active=..., child=body)` | Recebe o índice ativo e o widget já construído |

!!! warning "Aviso"
    O `TabView` **não** gerencia estado internamente — ele apenas renderiza o rótulo
    correto como ativo e dispara `on_change`. É responsabilidade do seu `view`
    persistir o índice no estado e passar o `child` correto.

---

## Passo 6 — Executar o app

Execute no **Modo A** (Python no browser via Pyodide):

```bash
tempestweb dev --mode wasm --path examples/tabs-profile
```

Execute no **Modo B** (Python no servidor via FastAPI + WebSocket):

```bash
tempestweb dev --mode server --path examples/tabs-profile
```

Abra `http://localhost:8000` no browser. Você deve ver:

- ✅ AppBar com o título "Profile";
- ✅ Três abas: Overview, Activity, Settings;
- ✅ Clicar em cada aba troca o conteúdo sem recarregar a página;
- ✅ Na aba Settings, os dois `Switch` respondem ao clique e o resumo em Overview
  reflete o novo estado.

---

## Recapitulando

Neste tutorial você construiu uma tela de perfil completa com três seções e aprendeu:

- 💡 **`TabView`** recebe `tabs` (rótulos), `active` (índice) e `on_change` (handler).
  Você passa o `child` já construído — o `TabView` não decide qual seção renderizar.
- 💡 **`RouteChangeEvent`** carrega o novo índice em `event.params["index"]`. Use
  `int(event.params.get("index", 0))` para convertê-lo com segurança.
- 💡 **`ToggleEvent`** carrega o novo booleano em `event.checked` — ideal para
  `Switch` em telas de configurações.
- 💡 **`Card` + `ListTile` + `Avatar` + `Divider`** formam um conjunto de componentes
  pré-construídos para layouts de lista ricos, sem CSS manual.
- 💡 O mesmo `app.py` roda nos dois modos — WASM e Servidor — sem nenhuma alteração.

---

## Próximos passos

- Veja o [tutorial central](../tutorial/index.md) para entender o ciclo de vida
  completo do tempestweb.
- Adicione navegação entre telas com o exemplo `router-push` (em breve).
- Explore animações de transição entre abas com o `AnimatedSwitcher`.
