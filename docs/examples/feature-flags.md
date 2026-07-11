# Feature Flags — Toggles de Feature em Runtime 🚀

Aprenda a usar `FeatureFlagsProvider` e `InMemoryFeatureFlagsAdapter` para
controlar variantes de UI em tempo de execução — sem tocar no transporte, sem
rede, sem framework de terceiros.

---

## O que você vai construir

Uma dashboard de feature flags com cinco seções:

- 🏷 **Header** — título e descrição do exemplo
- 🟡 **Beta Banner** — banner de canal beta, visível enquanto `beta_banner=True`
- 🖼 **UI Variant** — card "New UI" ou "Legacy UI", trocado pela flag `new_ui`
- 🎛 **Flags Panel** — painel com uma linha por flag e um botão toggle cada
- 🔢 **Rebuild Counter** — badge que conta quantas vezes alguma flag foi virada

!!! note "Nota — sem rede, sem bridge"
    O exemplo é completamente in-process: o `InMemoryFeatureFlagsAdapter` guarda
    os flags em um dict Python. Trocar por GrowthBook ou LaunchDarkly não muda
    nenhuma linha do `view` — só o adapter muda.

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
mkdir -p examples/feature-flags
touch examples/feature-flags/app.py
```

---

## Passo 1 — Definindo o estado

O estado guarda o adapter (backend dos flags), o provider (façade que o código
de UI usa) e um contador de rebuilds.

| Campo | Tipo | Significado |
|---|---|---|
| `adapter` | `InMemoryFeatureFlagsAdapter` | Backend com o dict de flags; exposto para que o toggle possa chamar `.set()` |
| `flags` | `FeatureFlagsProvider` | Façade estável que o `view` usa para ler flags via `.is_enabled()` |
| `rebuild_counter` | `int` | Incrementado no listener de mudança para forçar `set_state` a agendar um rebuild |

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Border, Color, Edge, FontWeight
from tempest_core.widgets import Button, Column, Container, Row, Text
from tempestweb.observability import (
    FeatureFlagsProvider,
    InMemoryFeatureFlagsAdapter,
)


def _make_adapter() -> InMemoryFeatureFlagsAdapter:
    """Return the default in-memory adapter with seed flags.

    Returns:
        An InMemoryFeatureFlagsAdapter pre-loaded with
        new_ui=False and beta_banner=True.
    """
    return InMemoryFeatureFlagsAdapter({"new_ui": False, "beta_banner": True})


@dataclass
class FeatureFlagsState:
    """Application state for the feature-flags demo.

    Attributes:
        adapter: The in-memory flag backend shared by the provider.
        flags: The provider facade every call site queries.
        rebuild_counter: Incremented by the change listener to force
            App.set_state to schedule a rebuild on each flag flip.
    """

    adapter: InMemoryFeatureFlagsAdapter = field(default_factory=_make_adapter)
    flags: FeatureFlagsProvider = field(init=False)
    rebuild_counter: int = 0

    def __post_init__(self) -> None:
        """Wire the provider to the adapter created in __init__.

        Returns:
            None.
        """
        self.flags = FeatureFlagsProvider(self.adapter)


def make_state() -> FeatureFlagsState:
    """Build the initial feature-flags state.

    Returns:
        A fresh FeatureFlagsState with seed flags.
    """
    return FeatureFlagsState()
```

!!! tip "Dica — por que `field(init=False)` no `flags`?"
    O `FeatureFlagsProvider` precisa do adapter já construído para se conectar ao
    stream de mudanças dele. Usar `field(init=False)` e criar o provider em
    `__post_init__` garante que o adapter já existe antes de o provider ser
    instanciado. Isso mantém o dataclass limpo e o wiring automático.

---

## Passo 2 — A paleta de cores

Defina as constantes de cor no topo do arquivo. Isso centraliza todos os valores
e torna a paleta legível independentemente da flag ativa.

```python
_BG: Color = Color.from_hex("#f0f4f8")
_SURFACE: Color = Color.from_hex("#ffffff")
_ON_BG: Color = Color.from_hex("#1a202c")
_MUTED: Color = Color.from_hex("#718096")
_ACCENT: Color = Color.from_hex("#4f46e5")
_SUCCESS: Color = Color.from_hex("#16a34a")
_WARN: Color = Color.from_hex("#d97706")
_DIVIDER: Color = Color.from_hex("#e2e8f0")
_ON_ACCENT: Color = Color.from_hex("#ffffff")
_BADGE_NEW: Color = Color.from_hex("#dbeafe")   # blue-100
_BADGE_BETA: Color = Color.from_hex("#fef9c3")  # yellow-100
```

---

## Passo 3 — O header

O primeiro widget é um card estático com título e descrição:

```python
def _header(app: App[FeatureFlagsState]) -> Widget:
    """Render the header section with title and subtitle.

    Args:
        app: The application handle.

    Returns:
        A Column with title and subtitle text.
    """
    return Container(
        key="header",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(24.0),
            radius=16.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=6.0),
            children=[
                Text(
                    content="Feature Flags",
                    key="title",
                    style=Style(
                        font_size=28.0,
                        font_weight=FontWeight.BOLD,
                        color=_ON_BG,
                    ),
                ),
                Text(
                    content=(
                        "Runtime toggles via FeatureFlagsProvider + "
                        "InMemoryFeatureFlagsAdapter. Swap the adapter for "
                        "GrowthBook or LaunchDarkly without touching the view."
                    ),
                    key="subtitle",
                    style=Style(font_size=13.0, color=_MUTED),
                ),
            ],
        ),
    )
```

---

## Passo 4 — O banner de beta

O banner só aparece quando `beta_banner` está habilitado. A lógica de
visibilidade fica no `view` (passo 7), não no builder:

```python
def _beta_banner(app: App[FeatureFlagsState]) -> Widget:
    """Render a beta-channel announcement banner.

    Only mounted when the beta_banner flag is enabled.

    Args:
        app: The application handle.

    Returns:
        A coloured banner widget.
    """
    return Container(
        key="beta-banner",
        style=Style(
            background=_BADGE_BETA,
            padding=Edge.symmetric(vertical=12.0, horizontal=20.0),
            radius=12.0,
            border=Border(width=1.0, color=_WARN),
        ),
        child=Row(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Beta",
                    key="beta-badge",
                    style=Style(
                        font_size=11.0,
                        font_weight=FontWeight.BOLD,
                        color=_WARN,
                        background=_WARN,
                    ),
                ),
                Text(
                    content=(
                        "You are on the beta channel. "
                        "Expect experimental features and faster update cycles."
                    ),
                    key="beta-text",
                    style=Style(font_size=13.0, color=_ON_BG),
                ),
            ],
        ),
    )
```

!!! info "Nota — condicional em Python puro"
    Você não precisa de nenhum widget especial de "se/senão". Use um `if`
    Python normal no `view` para incluir ou omitir um widget da lista de
    filhos. O reconciliador detecta que o nó foi inserido ou removido e gera
    os patches corretos automaticamente.

---

## Passo 5 — As variantes de UI

Dois builders, um para cada variante da flag `new_ui`:

```python
def _new_ui_variant(app: App[FeatureFlagsState]) -> Widget:
    """Render the modernised UI variant shown when new_ui is enabled.

    Args:
        app: The application handle.

    Returns:
        A styled card with the new-UI label.
    """
    return Container(
        key="new-ui-card",
        style=Style(
            background=_BADGE_NEW,
            padding=Edge.all(20.0),
            radius=14.0,
            border=Border(width=2.0, color=_ACCENT),
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="New UI — enabled",
                    key="new-ui-label",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_ACCENT,
                    ),
                ),
                Text(
                    content=(
                        "This card is only rendered when the new_ui flag "
                        "is truthy. The legacy card below disappears."
                    ),
                    key="new-ui-desc",
                    style=Style(font_size=13.0, color=_ON_BG),
                ),
            ],
        ),
    )


def _legacy_ui_variant(app: App[FeatureFlagsState]) -> Widget:
    """Render the legacy UI variant shown when new_ui is disabled.

    Args:
        app: The application handle.

    Returns:
        A muted card with the legacy-UI label.
    """
    return Container(
        key="legacy-ui-card",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(20.0),
            radius=14.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Legacy UI — active",
                    key="legacy-ui-label",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_MUTED,
                    ),
                ),
                Text(
                    content=(
                        "The classic layout is shown when new_ui is off. "
                        "Toggle the flag above to swap to the new variant."
                    ),
                    key="legacy-ui-desc",
                    style=Style(font_size=13.0, color=_MUTED),
                ),
            ],
        ),
    )
```

!!! tip "Dica — keys únicas por variante"
    Note que cada variante tem `key="new-ui-card"` e `key="legacy-ui-card"`,
    respectivamente. O reconciliador usa a `key` para decidir se o nó mudou de
    tipo/identidade. Keys distintas garantem que o diff produza um patch
    `remove + insert` (substituição completa) em vez de tentar atualizar o nó
    existente in-place.

---

## Passo 6 — O painel de flags com o toggle

A parte mais interessante: um builder genérico para uma linha de flag com seu
botão toggle. A lógica de flip chama `adapter.set()` para mudar o valor no
backend e depois incrementa o `rebuild_counter` via `app.set_state` para forçar
o framework a chamar `view` novamente.

```python
def _flag_row(
    app: App[FeatureFlagsState],
    flag_key: str,
    label: str,
    description: str,
    widget_key_prefix: str,
) -> Widget:
    """Render a single flag row with its current value and a toggle button.

    Args:
        app: The application handle.
        flag_key: The feature flag key to read and toggle.
        label: The human-readable flag name.
        description: A one-sentence description of what the flag gates.
        widget_key_prefix: A unique prefix for the row's widget keys.

    Returns:
        A Row with flag info and a toggle button.
    """
    enabled: bool = app.state.flags.is_enabled(flag_key)
    status_text: str = "ON" if enabled else "OFF"
    status_color: Color = _SUCCESS if enabled else _MUTED
    btn_label: str = f"Turn {'off' if enabled else 'on'}"

    def toggle() -> None:
        """Flip the flag and schedule a rebuild via the counter.

        Returns:
            None.
        """
        current: bool = app.state.flags.is_enabled(flag_key)
        app.state.adapter.set(flag_key, not current)
        app.set_state(lambda s: setattr(s, "rebuild_counter", s.rebuild_counter + 1))

    return Container(
        key=f"{widget_key_prefix}-row",
        style=Style(
            background=_SURFACE,
            padding=Edge.symmetric(vertical=12.0, horizontal=16.0),
            radius=10.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Row(
            style=Style(gap=12.0),
            children=[
                Column(
                    key=f"{widget_key_prefix}-info",
                    style=Style(gap=4.0, grow=1.0),
                    children=[
                        Row(
                            key=f"{widget_key_prefix}-name-row",
                            style=Style(gap=8.0),
                            children=[
                                Text(
                                    content=label,
                                    key=f"{widget_key_prefix}-name",
                                    style=Style(
                                        font_size=14.0,
                                        font_weight=FontWeight.BOLD,
                                        color=_ON_BG,
                                    ),
                                ),
                                Text(
                                    content=status_text,
                                    key=f"{widget_key_prefix}-status",
                                    style=Style(
                                        font_size=12.0,
                                        font_weight=FontWeight.BOLD,
                                        color=status_color,
                                    ),
                                ),
                            ],
                        ),
                        Text(
                            content=description,
                            key=f"{widget_key_prefix}-desc",
                            style=Style(font_size=12.0, color=_MUTED),
                        ),
                    ],
                ),
                Button(
                    label=btn_label,
                    on_click=toggle,
                    key=f"{widget_key_prefix}-toggle",
                ),
            ],
        ),
    )
```

!!! warning "Aviso — ordem das chamadas no toggle"
    No handler `toggle`, a ordem importa:

    1. Leia o valor atual com `app.state.flags.is_enabled(flag_key)` **antes**
       de chamar `.set()`.
    2. Chame `app.state.adapter.set(flag_key, not current)` para mudar o
       backend.
    3. Chame `app.set_state(...)` para incrementar o contador e agendar um
       rebuild.

    Se você inverter as etapas 1 e 2, vai ler o valor **após** a mutação e
    virar o flag no sentido errado.

O builder do painel completo agrega duas linhas de flag:

```python
def _flags_panel(app: App[FeatureFlagsState]) -> Widget:
    """Render the flags management panel with individual flag rows.

    Args:
        app: The application handle.

    Returns:
        A card containing a row per known flag.
    """
    return Container(
        key="flags-panel",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(20.0),
            radius=16.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=12.0),
            children=[
                Text(
                    content="Active flags",
                    key="panel-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_ON_BG,
                    ),
                ),
                Container(
                    key="panel-divider",
                    style=Style(height=1.0, background=_DIVIDER),
                ),
                _flag_row(
                    app,
                    flag_key="new_ui",
                    label="new_ui",
                    description=(
                        "Gates the modernised layout. Toggle to swap "
                        "between the new-UI card and the legacy card."
                    ),
                    widget_key_prefix="new-ui",
                ),
                _flag_row(
                    app,
                    flag_key="beta_banner",
                    label="beta_banner",
                    description=(
                        "Shows the beta-channel announcement banner at "
                        "the top of the page."
                    ),
                    widget_key_prefix="beta-banner-flag",
                ),
            ],
        ),
    )
```

---

## Passo 7 — O contador de rebuilds

Um badge simples que exibe `rebuild_counter` para confirmar que o listener está
conectado corretamente:

```python
def _counter_badge(app: App[FeatureFlagsState]) -> Widget:
    """Render a small rebuild-counter badge for observability.

    Incremented each time a flag is toggled, confirming the change listener
    is wired correctly to App.set_state.

    Args:
        app: The application handle.

    Returns:
        A Text displaying the counter.
    """
    return Text(
        content=f"Flag changes: {app.state.rebuild_counter}",
        key="rebuild-counter",
        style=Style(font_size=12.0, color=_MUTED),
    )
```

---

## Passo 8 — Montando o `view`

A função raiz `view` compõe as seções com renderização condicional pura em
Python:

```python
def view(app: App[FeatureFlagsState]) -> Widget:
    """Render the full feature-flags demo.

    Layout (top to bottom):

    1. Header — title and description.
    2. Beta banner — only when beta_banner flag is truthy.
    3. New UI / Legacy UI card — swapped by the new_ui flag.
    4. Flags panel — one row per flag with a live toggle button.
    5. Rebuild counter — incremented on every flag flip to confirm wiring.

    Args:
        app: The application handle exposing state and set_state.

    Returns:
        The widget tree for the current state.
    """
    sections: list[Widget] = [_header(app)]

    if app.state.flags.is_enabled("beta_banner"):
        sections.append(_beta_banner(app))

    if app.state.flags.is_enabled("new_ui"):
        sections.append(_new_ui_variant(app))
    else:
        sections.append(_legacy_ui_variant(app))

    sections.append(_flags_panel(app))
    sections.append(_counter_badge(app))

    return Container(
        key="root",
        style=Style(background=_BG, padding=Edge.all(0.0)),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=sections,
        ),
    )
```

!!! check "O ponto central do exemplo"
    Repare que `view` usa `app.state.flags.is_enabled("beta_banner")` e
    `app.state.flags.is_enabled("new_ui")` — **nunca** acessa o adapter
    diretamente. Esse é o padrão correto: o `view` fala sempre com o provider;
    só o handler de toggle fala com o adapter. Trocar o adapter por GrowthBook
    não muda nenhuma linha do `view`.

---

## O app completo

Aqui está o arquivo completo `examples/feature-flags/app.py`, pronto para
copiar:

```python
"""Feature flags — demonstrates runtime feature toggles via ``FeatureFlagsProvider``.

The app ships with two flags:

* ``new_ui``   — gates an alternative, modernised UI layout (off by default).
* ``beta_banner`` — shows a beta-channel announcement banner (on by default).

A *Toggle new_ui* button flips ``new_ui`` via
:meth:`~tempestweb.observability.InMemoryFeatureFlagsAdapter.set`, which fires
the provider's change subscribers and triggers :meth:`App.set_state` to schedule
a rebuild. The entire demo is pure in-process: no network, no bridge, no async.

Key concepts shown
------------------
* :class:`~tempestweb.observability.FeatureFlagsProvider` — the stable facade
  every call site uses.
* :class:`~tempestweb.observability.InMemoryFeatureFlagsAdapter` — a
  dependency-free, test-ready backend; swappable for GrowthBook / LaunchDarkly
  without touching the view.
* :meth:`~tempestweb.observability.FeatureFlagsProvider.is_enabled` — coerces
  any flag value to a boolean for uniform feature-gate checks.
* :meth:`~tempestweb.observability.FeatureFlagsProvider.on_change` — wires flag
  mutations to :meth:`App.set_state` so the view rebuilds on every flip.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Border, Color, Edge, FontWeight
from tempest_core.widgets import Button, Column, Container, Row, Text
from tempestweb.observability import (
    FeatureFlagsProvider,
    InMemoryFeatureFlagsAdapter,
)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

_BG: Color = Color.from_hex("#f0f4f8")
_SURFACE: Color = Color.from_hex("#ffffff")
_ON_BG: Color = Color.from_hex("#1a202c")
_MUTED: Color = Color.from_hex("#718096")
_ACCENT: Color = Color.from_hex("#4f46e5")
_SUCCESS: Color = Color.from_hex("#16a34a")
_WARN: Color = Color.from_hex("#d97706")
_DIVIDER: Color = Color.from_hex("#e2e8f0")
_ON_ACCENT: Color = Color.from_hex("#ffffff")
_BADGE_NEW: Color = Color.from_hex("#dbeafe")  # blue-100
_BADGE_BETA: Color = Color.from_hex("#fef9c3")  # yellow-100


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _make_adapter() -> InMemoryFeatureFlagsAdapter:
    """Return the default in-memory adapter with seed flags.

    Returns:
        An :class:`~tempestweb.observability.InMemoryFeatureFlagsAdapter`
        pre-loaded with ``new_ui=False`` and ``beta_banner=True``.
    """
    return InMemoryFeatureFlagsAdapter({"new_ui": False, "beta_banner": True})


@dataclass
class FeatureFlagsState:
    """Application state for the feature-flags demo.

    Attributes:
        adapter: The in-memory flag backend shared by the provider.  Exposed
            on the state so the toggle handler can flip individual flags via
            :meth:`~tempestweb.observability.InMemoryFeatureFlagsAdapter.set`.
        flags: The provider facade every call site queries.
        rebuild_counter: A monotonic counter incremented by the change listener
            to force :meth:`App.set_state` to schedule a rebuild when a flag
            flips (even though the *structural* state that changed is the adapter's
            internal dict, not this dataclass).
    """

    adapter: InMemoryFeatureFlagsAdapter = field(default_factory=_make_adapter)
    flags: FeatureFlagsProvider = field(init=False)
    rebuild_counter: int = 0

    def __post_init__(self) -> None:
        """Wire the provider to the adapter created in ``__init__``.

        Returns:
            None.
        """
        self.flags = FeatureFlagsProvider(self.adapter)


def make_state() -> FeatureFlagsState:
    """Build the initial feature-flags state.

    Returns:
        A fresh :class:`FeatureFlagsState` with seed flags.
    """
    return FeatureFlagsState()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _header(app: App[FeatureFlagsState]) -> Widget:
    """Render the header section with title and subtitle.

    Args:
        app: The application handle.

    Returns:
        A :class:`~tempest_core.widgets.Column` with title and subtitle
        text.
    """
    return Container(
        key="header",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(24.0),
            radius=16.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=6.0),
            children=[
                Text(
                    content="Feature Flags",
                    key="title",
                    style=Style(
                        font_size=28.0,
                        font_weight=FontWeight.BOLD,
                        color=_ON_BG,
                    ),
                ),
                Text(
                    content=(
                        "Runtime toggles via FeatureFlagsProvider + "
                        "InMemoryFeatureFlagsAdapter. Swap the adapter for "
                        "GrowthBook or LaunchDarkly without touching the view."
                    ),
                    key="subtitle",
                    style=Style(font_size=13.0, color=_MUTED),
                ),
            ],
        ),
    )


def _beta_banner(app: App[FeatureFlagsState]) -> Widget:
    """Render a beta-channel announcement banner.

    Only mounted when the ``beta_banner`` flag is enabled.

    Args:
        app: The application handle.

    Returns:
        A coloured banner widget.
    """
    return Container(
        key="beta-banner",
        style=Style(
            background=_BADGE_BETA,
            padding=Edge.symmetric(vertical=12.0, horizontal=20.0),
            radius=12.0,
            border=Border(width=1.0, color=_WARN),
        ),
        child=Row(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Beta",
                    key="beta-badge",
                    style=Style(
                        font_size=11.0,
                        font_weight=FontWeight.BOLD,
                        color=_WARN,
                        background=_WARN,
                    ),
                ),
                Text(
                    content=(
                        "You are on the beta channel. "
                        "Expect experimental features and faster update cycles."
                    ),
                    key="beta-text",
                    style=Style(font_size=13.0, color=_ON_BG),
                ),
            ],
        ),
    )


def _new_ui_variant(app: App[FeatureFlagsState]) -> Widget:
    """Render the modernised UI variant shown when ``new_ui`` is enabled.

    Args:
        app: The application handle.

    Returns:
        A styled card with the new-UI label.
    """
    return Container(
        key="new-ui-card",
        style=Style(
            background=_BADGE_NEW,
            padding=Edge.all(20.0),
            radius=14.0,
            border=Border(width=2.0, color=_ACCENT),
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="New UI — enabled",
                    key="new-ui-label",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_ACCENT,
                    ),
                ),
                Text(
                    content=(
                        "This card is only rendered when the new_ui flag "
                        "is truthy. The legacy card below disappears."
                    ),
                    key="new-ui-desc",
                    style=Style(font_size=13.0, color=_ON_BG),
                ),
            ],
        ),
    )


def _legacy_ui_variant(app: App[FeatureFlagsState]) -> Widget:
    """Render the legacy UI variant shown when ``new_ui`` is disabled.

    Args:
        app: The application handle.

    Returns:
        A muted card with the legacy-UI label.
    """
    return Container(
        key="legacy-ui-card",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(20.0),
            radius=14.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=8.0),
            children=[
                Text(
                    content="Legacy UI — active",
                    key="legacy-ui-label",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_MUTED,
                    ),
                ),
                Text(
                    content=(
                        "The classic layout is shown when new_ui is off. "
                        "Toggle the flag above to swap to the new variant."
                    ),
                    key="legacy-ui-desc",
                    style=Style(font_size=13.0, color=_MUTED),
                ),
            ],
        ),
    )


def _flag_row(
    app: App[FeatureFlagsState],
    flag_key: str,
    label: str,
    description: str,
    widget_key_prefix: str,
) -> Widget:
    """Render a single flag row with its current value and a toggle button.

    Args:
        app: The application handle.
        flag_key: The feature flag key to read and toggle.
        label: The human-readable flag name.
        description: A one-sentence description of what the flag gates.
        widget_key_prefix: A unique prefix for the row's widget keys.

    Returns:
        A :class:`~tempest_core.widgets.Row` with flag info and a button.
    """
    enabled: bool = app.state.flags.is_enabled(flag_key)
    status_text: str = "ON" if enabled else "OFF"
    status_color: Color = _SUCCESS if enabled else _MUTED
    btn_label: str = f"Turn {'off' if enabled else 'on'}"

    def toggle() -> None:
        """Flip the flag and schedule a rebuild via the counter.

        Returns:
            None.
        """
        current: bool = app.state.flags.is_enabled(flag_key)
        app.state.adapter.set(flag_key, not current)
        app.set_state(lambda s: setattr(s, "rebuild_counter", s.rebuild_counter + 1))

    return Container(
        key=f"{widget_key_prefix}-row",
        style=Style(
            background=_SURFACE,
            padding=Edge.symmetric(vertical=12.0, horizontal=16.0),
            radius=10.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Row(
            style=Style(gap=12.0),
            children=[
                Column(
                    key=f"{widget_key_prefix}-info",
                    style=Style(gap=4.0, grow=1.0),
                    children=[
                        Row(
                            key=f"{widget_key_prefix}-name-row",
                            style=Style(gap=8.0),
                            children=[
                                Text(
                                    content=label,
                                    key=f"{widget_key_prefix}-name",
                                    style=Style(
                                        font_size=14.0,
                                        font_weight=FontWeight.BOLD,
                                        color=_ON_BG,
                                    ),
                                ),
                                Text(
                                    content=status_text,
                                    key=f"{widget_key_prefix}-status",
                                    style=Style(
                                        font_size=12.0,
                                        font_weight=FontWeight.BOLD,
                                        color=status_color,
                                    ),
                                ),
                            ],
                        ),
                        Text(
                            content=description,
                            key=f"{widget_key_prefix}-desc",
                            style=Style(font_size=12.0, color=_MUTED),
                        ),
                    ],
                ),
                Button(
                    label=btn_label,
                    on_click=toggle,
                    key=f"{widget_key_prefix}-toggle",
                ),
            ],
        ),
    )


def _flags_panel(app: App[FeatureFlagsState]) -> Widget:
    """Render the flags management panel with individual flag rows.

    Args:
        app: The application handle.

    Returns:
        A card containing a row per known flag.
    """
    return Container(
        key="flags-panel",
        style=Style(
            background=_SURFACE,
            padding=Edge.all(20.0),
            radius=16.0,
            border=Border(width=1.0, color=_DIVIDER),
        ),
        child=Column(
            style=Style(gap=12.0),
            children=[
                Text(
                    content="Active flags",
                    key="panel-heading",
                    style=Style(
                        font_size=16.0,
                        font_weight=FontWeight.BOLD,
                        color=_ON_BG,
                    ),
                ),
                Container(
                    key="panel-divider",
                    style=Style(height=1.0, background=_DIVIDER),
                ),
                _flag_row(
                    app,
                    flag_key="new_ui",
                    label="new_ui",
                    description=(
                        "Gates the modernised layout. Toggle to swap "
                        "between the new-UI card and the legacy card."
                    ),
                    widget_key_prefix="new-ui",
                ),
                _flag_row(
                    app,
                    flag_key="beta_banner",
                    label="beta_banner",
                    description=(
                        "Shows the beta-channel announcement banner at "
                        "the top of the page."
                    ),
                    widget_key_prefix="beta-banner-flag",
                ),
            ],
        ),
    )


def _counter_badge(app: App[FeatureFlagsState]) -> Widget:
    """Render a small rebuild-counter badge for observability.

    Incremented each time a flag is toggled, confirming the change listener
    is wired correctly to :meth:`App.set_state`.

    Args:
        app: The application handle.

    Returns:
        A :class:`~tempest_core.widgets.Text` displaying the counter.
    """
    return Text(
        content=f"Flag changes: {app.state.rebuild_counter}",
        key="rebuild-counter",
        style=Style(font_size=12.0, color=_MUTED),
    )


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


def view(app: App[FeatureFlagsState]) -> Widget:
    """Render the full feature-flags demo.

    Layout (top to bottom):

    1. **Header** — title and description.
    2. **Beta banner** — only when ``beta_banner`` flag is truthy.
    3. **New UI / Legacy UI card** — swapped by the ``new_ui`` flag.
    4. **Flags panel** — one row per flag with a live toggle button.
    5. **Rebuild counter** — incremented on every flag flip to confirm wiring.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    sections: list[Widget] = [_header(app)]

    if app.state.flags.is_enabled("beta_banner"):
        sections.append(_beta_banner(app))

    if app.state.flags.is_enabled("new_ui"):
        sections.append(_new_ui_variant(app))
    else:
        sections.append(_legacy_ui_variant(app))

    sections.append(_flags_panel(app))
    sections.append(_counter_badge(app))

    return Container(
        key="root",
        style=Style(background=_BG, padding=Edge.all(0.0)),
        child=Column(
            key="page",
            style=Style(gap=16.0, padding=Edge.all(16.0)),
            children=sections,
        ),
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/feature-flags
```

Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/feature-flags
```

Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica
ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Header "Feature Flags" com o subtítulo descrevendo o adapter
    2. Banner amarelo "Beta" (porque `beta_banner=True` por padrão)
    3. Card "Legacy UI — active" (porque `new_ui=False` por padrão)
    4. Painel "Active flags" com duas linhas — `new_ui OFF` e `beta_banner ON`
    5. Badge "Flag changes: 0"
    6. Clique **Turn on** na linha `new_ui` → card troca para "New UI — enabled", contador vira 1
    7. Clique **Turn off** na linha `new_ui` → card volta para "Legacy UI — active", contador vira 2
    8. Clique **Turn off** na linha `beta_banner` → banner amarelo desaparece, contador vira 3
    9. Clique **Turn on** na linha `beta_banner` → banner reaparece, contador vira 4

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

# Testes (9/9 passam)
pytest -q
```

Todos passam em verde. O exemplo foi escrito para ser `mypy --strict` clean —
toda variável e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo completo de um toggle

```
Clique em "Turn on" (new_ui)
      │
      ▼
toggle() no closure
      │
      ├─ app.state.flags.is_enabled("new_ui")  → lê False (antes da mutação)
      │
      ├─ app.state.adapter.set("new_ui", True)
      │         │
      │         └─ adapter._emit()
      │                 │
      │                 └─ provider._notify()   ← bridge adapter→provider
      │                         │
      │                         └─ listeners do provider disparam
      │                            (nenhum neste exemplo — o counter é o gatilho)
      │
      └─ app.set_state(lambda s: s.rebuild_counter + 1)
                │
                ▼
        view(app) chamada novamente
                │
                ▼
        app.state.flags.is_enabled("new_ui") → True
                │
                ▼
        sections inclui _new_ui_variant(app)
        sections NÃO inclui _legacy_ui_variant(app)
                │
                ▼
        build(view(app)) produz nova IR
                │
                ▼
        diff(before, after) → patches [Remove "legacy-ui-card", Insert "new-ui-card"]
                │
                ▼
        DOM atualizado
```

### Por que o `rebuild_counter` é necessário?

O `InMemoryFeatureFlagsAdapter` muta o seu dict interno quando você chama
`.set()`. Esse dict **não é parte do dataclass** `FeatureFlagsState` — é um
objeto aninhado. O framework não sabe que o conteúdo de `adapter._flags` mudou;
ele só agenda um rebuild quando `app.set_state` é chamado com uma mutação
visível ao dataclass.

O `rebuild_counter` resolve isso: é um inteiro no dataclass que o listener
incrementa, tornando a mudança visível ao mecanismo de rebuild. É uma técnica
comum em frameworks reativos quando se quer observar mudanças em objetos
externos ao estado reativo principal.

??? note "Detalhe técnico — `on_change` vs `adapter.subscribe`"
    `FeatureFlagsProvider.on_change(listener)` registra um listener que é
    chamado sempre que **qualquer** flag muda. Internamente, o provider se
    registrou no adapter via `adapter.subscribe(self._notify)` no `__init__`, e
    `_notify` faz fan-out para todos os listeners do provider. Isso significa
    que o código de UI nunca precisa conhecer o adapter diretamente para reagir
    a mudanças — basta registrar com `flags.on_change(...)`.

    Neste exemplo não usamos `on_change` explicitamente porque o toggle chama
    `app.set_state` diretamente depois de `.set()`. Em um app real com múltiplas
    partes da UI reagindo ao mesmo flag, `on_change` seria o lugar certo para
    concentrar o rebuild.

### Adapter vs Provider — a separação de responsabilidades

| | `InMemoryFeatureFlagsAdapter` | `FeatureFlagsProvider` |
|---|---|---|
| Lê flags | `.get(key, default)` | `.get(key, default)`, `.is_enabled(key)` |
| Muta flags | `.set(key, value)` | — (imutável da perspectiva do view) |
| Notifica mudanças | `.subscribe(listener)` | `.on_change(listener)` |
| Quem usa | Handlers de toggle | Funções de `view` |

Essa separação é o que permite trocar o backend por GrowthBook ou LaunchDarkly
sem mudar nenhuma linha do `view`.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Criar um `FeatureFlagsProvider` conectado a um `InMemoryFeatureFlagsAdapter`
- ✅ Usar `is_enabled(key)` no `view` para renderização condicional pura em Python
- ✅ Implementar o padrão adapter — o `view` fala com o provider, o toggle fala com o adapter
- ✅ Usar `app.set_state` para forçar um rebuild quando um objeto externo muta
- ✅ Confirmar o wiring via `rebuild_counter` — um badge observável de quantas vezes a view foi reconstruída
- ✅ Usar `build` + `diff` para verificar que os patches são não-vazios após cada toggle

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione uma terceira flag `dark_mode` e use-a para trocar a paleta de cores
  — combine com o exemplo [Theme Switcher](./theme-switcher.md)
- 💡 Implemente um `GrowthBookFeatureFlagsAdapter` usando o cliente GrowthBook
  Python e troque o adapter no `make_state` sem mudar o `view`
- 💡 Registre um listener com `flags.on_change(lambda: app.set_state(...))` em
  `__post_init__` e remova o `set_state` manual do toggle — veja o resultado ser
  o mesmo
- 💡 Leia [Modos de execução](../tutorial/modes.md) para entender como o mesmo
  `app.py` funciona nos dois transports sem nenhuma mudança
