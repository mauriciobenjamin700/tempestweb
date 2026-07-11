# Profile cards — avatar, rating e accordion 🚀

Neste exemplo você vai construir uma tela de **diretório de equipe** usando os
componentes de exibição e disclosure do core: `Avatar` e `Rating` dentro de
`Card` de perfil, um `Accordion` de seções expansíveis, e `ListTile` separados
por `Divider`. Tocar numa estrela grava a nota; abrir uma seção do accordion é
controlado pelo estado.

---

## O que você vai construir

- 👤 **Cards de perfil** com `Avatar` (iniciais) e `Rating` interativo.
- ⭐ Um `Rating` que chama `on_rate(stars)` ao clicar numa estrela.
- 📂 Um **Accordion** de seções expansíveis (`open` + `on_toggle`).
- 📋 Linhas de **ListTile** separadas por **Divider**.

---

## Pré-requisitos

```bash
pip install tempestweb
```

!!! tip "Dica"
    Se você ainda não conhece o ciclo estado → view → patches, leia o
    [tutorial de introdução](../tutorial/index.md).

---

## Passo 1 — O perfil e o estado

Cada membro é um `Profile` mutável (a nota muda). O estado guarda a lista de
perfis e o `slug` da seção aberta do accordion (ou `None`).

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Profile:
    """A single team member shown as a profile card.

    Attributes:
        slug: Stable identifier used for widget keys and state lookups.
        name: Display name shown as the card heading.
        role: Job title shown beneath the name.
        initials: Two-letter monogram rendered inside the avatar.
        rating: Current star score (0..5), mutated by ``Rating.on_rate``.
    """

    slug: str
    name: str
    role: str
    initials: str
    rating: int


@dataclass
class ProfileCardsState:
    """State for the profile-cards screen.

    Attributes:
        profiles: The team members rendered as profile cards.
        open_section: The ``slug`` of the accordion section currently open,
            or ``None`` when every section is collapsed.
    """

    profiles: list[Profile] = field(default_factory=list)
    open_section: str | None = "skills"


def make_state() -> ProfileCardsState:
    """Build the initial state.

    Returns:
        A fresh :class:`ProfileCardsState` pre-populated with a few profiles.
    """
    return ProfileCardsState(
        profiles=[
            Profile(
                slug="ana",
                name="Ana Ribeiro",
                role="Staff Engineer",
                initials="AR",
                rating=5,
            ),
            Profile(
                slug="bruno",
                name="Bruno Costa",
                role="Product Designer",
                initials="BC",
                rating=4,
            ),
            Profile(
                slug="carla",
                name="Carla Nunes",
                role="Data Scientist",
                initials="CN",
                rating=3,
            ),
        ],
    )
```

!!! note "Nota — `slug` como chave estável"
    Cada perfil tem um `slug` que serve tanto para as `key` dos widgets quanto
    para localizar o perfil certo na hora de gravar a nota. Chaves estáveis fazem
    o reconciliador atualizar o nó correto.

---

## Passo 2 — O card de perfil com rating interativo

O `Rating` recebe `value` (nota atual), `max_stars` e `on_rate`. O handler `rate`
encontra o perfil pelo `slug` e grava a nova nota.

```python
from tempest_core import App, Column, Row, Style, Text, Widget
from tempestweb.components import Avatar, Card, Rating

def _profile_card(app: App[ProfileCardsState], profile: Profile) -> Widget:
    """Render one profile card with an avatar and an interactive rating."""

    def rate(stars: int) -> None:
        """Record a new star score for this profile."""

        def apply(state: ProfileCardsState) -> None:
            for candidate in state.profiles:
                if candidate.slug == profile.slug:
                    candidate.rating = stars
                    break

        app.set_state(apply)

    return Card(
        key=f"card-{profile.slug}",
        color_scheme="primary",
        children=[
            Row(
                style=Style(gap=12.0),
                children=[
                    Avatar(
                        key=f"avatar-{profile.slug}",
                        initials=profile.initials,
                        size=48.0,
                    ),
                    Column(
                        style=Style(gap=2.0),
                        children=[
                            Text(
                                content=profile.name,
                                key=f"name-{profile.slug}",
                            ),
                            Text(
                                content=profile.role,
                                key=f"role-{profile.slug}",
                            ),
                        ],
                    ),
                ],
            ),
            Rating(
                key=f"rating-{profile.slug}",
                value=profile.rating,
                max_stars=5,
                on_rate=rate,
            ),
        ],
    )
```

---

## Passo 3 — A listagem dentro do accordion

`ListTile` (com `title` + `subtitle`) separados por `Divider` formam o corpo de
uma seção.

```python
from tempest_core import Column, Style
from tempestweb.components import Divider, ListTile

def _detail_listing() -> Widget:
    """Render the static detail listing shown inside the accordion body."""
    return Column(
        style=Style(gap=4.0),
        children=[
            ListTile(
                key="skill-python",
                title="Python",
                subtitle="Async-first backend services",
            ),
            Divider(key="div-1"),
            ListTile(
                key="skill-typescript",
                title="TypeScript",
                subtitle="Type-safe client interfaces",
            ),
            Divider(key="div-2"),
            ListTile(
                key="skill-sql",
                title="SQL",
                subtitle="PostgreSQL & query tuning",
            ),
        ],
    )
```

---

## Passo 4 — O accordion controlado por estado

`Accordion` recebe `title`, `open` (booleano derivado do estado) e `on_toggle`. O
handler `toggle` abre a seção clicada ou fecha se ela já estava aberta.

```python
def toggle(section: str) -> None:
    """Open the given accordion section or collapse it if already open."""

    def apply(state: ProfileCardsState) -> None:
        state.open_section = None if state.open_section == section else section

    app.set_state(apply)
```

!!! info "Info — accordion exclusivo com um único campo"
    Guardando apenas `open_section: str | None`, garantimos que **no máximo uma**
    seção fica aberta por vez. `open=app.state.open_section == "skills"` deriva o
    estado de cada seção desse único campo.

---

## O app completo

```python
"""Core profile cards — showcasing display & disclosure components.

This example renders a small team-directory screen built entirely from the
core's display/disclosure components: :class:`Avatar` and :class:`Rating`
inside profile :class:`Card` widgets, an :class:`Accordion` of expandable
detail sections, and :class:`ListTile` rows separated by :class:`Divider`.

The same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

Interaction is wired through state: tapping a star calls ``Rating.on_rate``
to record a new score, and toggling a section header calls
``Accordion.on_toggle`` to open or close it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
from tempestweb.components import (
    Accordion,
    Avatar,
    Card,
    Divider,
    ListTile,
    Rating,
)


@dataclass
class Profile:
    """A single team member shown as a profile card.

    Attributes:
        slug: Stable identifier used for widget keys and state lookups.
        name: Display name shown as the card heading.
        role: Job title shown beneath the name.
        initials: Two-letter monogram rendered inside the avatar.
        rating: Current star score (0..5), mutated by ``Rating.on_rate``.
    """

    slug: str
    name: str
    role: str
    initials: str
    rating: int


@dataclass
class ProfileCardsState:
    """State for the profile-cards screen.

    Attributes:
        profiles: The team members rendered as profile cards.
        open_section: The ``slug`` of the accordion section currently open,
            or ``None`` when every section is collapsed.
    """

    profiles: list[Profile] = field(default_factory=list)
    open_section: str | None = "skills"


def make_state() -> ProfileCardsState:
    """Build the initial state.

    Returns:
        A fresh :class:`ProfileCardsState` pre-populated with a few profiles.
    """
    return ProfileCardsState(
        profiles=[
            Profile(
                slug="ana",
                name="Ana Ribeiro",
                role="Staff Engineer",
                initials="AR",
                rating=5,
            ),
            Profile(
                slug="bruno",
                name="Bruno Costa",
                role="Product Designer",
                initials="BC",
                rating=4,
            ),
            Profile(
                slug="carla",
                name="Carla Nunes",
                role="Data Scientist",
                initials="CN",
                rating=3,
            ),
        ],
    )


def _profile_card(app: App[ProfileCardsState], profile: Profile) -> Widget:
    """Render one profile card with an avatar and an interactive rating.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.
        profile: The team member to render.

    Returns:
        A :class:`Card` widget for the given profile.
    """

    def rate(stars: int) -> None:
        """Record a new star score for this profile.

        Args:
            stars: The number of stars selected by the user (1..5).
        """

        def apply(state: ProfileCardsState) -> None:
            for candidate in state.profiles:
                if candidate.slug == profile.slug:
                    candidate.rating = stars
                    break

        app.set_state(apply)

    return Card(
        key=f"card-{profile.slug}",
        color_scheme="primary",
        children=[
            Row(
                style=Style(gap=12.0),
                children=[
                    Avatar(
                        key=f"avatar-{profile.slug}",
                        initials=profile.initials,
                        size=48.0,
                    ),
                    Column(
                        style=Style(gap=2.0),
                        children=[
                            Text(
                                content=profile.name,
                                key=f"name-{profile.slug}",
                            ),
                            Text(
                                content=profile.role,
                                key=f"role-{profile.slug}",
                            ),
                        ],
                    ),
                ],
            ),
            Rating(
                key=f"rating-{profile.slug}",
                value=profile.rating,
                max_stars=5,
                on_rate=rate,
            ),
        ],
    )


def _detail_listing() -> Widget:
    """Render the static detail listing shown inside the accordion body.

    Returns:
        A :class:`Column` of :class:`ListTile` rows separated by dividers.
    """
    return Column(
        style=Style(gap=4.0),
        children=[
            ListTile(
                key="skill-python",
                title="Python",
                subtitle="Async-first backend services",
            ),
            Divider(key="div-1"),
            ListTile(
                key="skill-typescript",
                title="TypeScript",
                subtitle="Type-safe client interfaces",
            ),
            Divider(key="div-2"),
            ListTile(
                key="skill-sql",
                title="SQL",
                subtitle="PostgreSQL & query tuning",
            ),
        ],
    )


def view(app: App[ProfileCardsState]) -> Widget:
    """Render the profile-cards screen from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def toggle(section: str) -> None:
        """Open the given accordion section or collapse it if already open.

        Args:
            section: The ``slug`` of the section that was toggled.
        """

        def apply(state: ProfileCardsState) -> None:
            state.open_section = None if state.open_section == section else section

        app.set_state(apply)

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content="Team Directory", key="heading"),
            *[_profile_card(app, profile) for profile in app.state.profiles],
            Accordion(
                key="acc-skills",
                title="Shared skills",
                open=app.state.open_section == "skills",
                on_toggle=lambda: toggle("skills"),
                children=[_detail_listing()],
            ),
            Accordion(
                key="acc-contact",
                title="Contact channels",
                open=app.state.open_section == "contact",
                on_toggle=lambda: toggle("contact"),
                children=[
                    Column(
                        style=Style(gap=4.0),
                        children=[
                            ListTile(
                                key="contact-email",
                                title="Email",
                                subtitle="team@example.com",
                            ),
                            Divider(key="div-contact"),
                            ListTile(
                                key="contact-slack",
                                title="Slack",
                                subtitle="#team-directory",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

=== "Modo A — WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/core-profile-cards
    ```

=== "Modo B — Servidor (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/core-profile-cards
    ```

!!! check "Verificação"
    Você deve ver três cards de perfil com avatares e estrelas. Clique numa
    estrela → a nota daquele perfil atualiza. Clique no cabeçalho "Contact
    channels" → a seção abre e "Shared skills" fecha. ✅

---

## Recapitulando

- ✅ Renderizar perfis com `Avatar` (`initials`/`size`) e `Rating` interativo.
- ✅ Gravar a nota com `on_rate(stars)`, localizando o perfil pelo `slug`.
- ✅ Compor disclosure com `Accordion` (`open`/`on_toggle`) exclusivo.
- ✅ Listar detalhes com `ListTile` + `Divider`.
- ✅ Rodar o mesmo `app.py` nos dois modos sem alterar uma linha.

!!! tip "Próximos passos"
    - Veja [Avaliação e review](rating-review.md) para mais foco no `Rating`.
    - Combine com [FAQ accordion](faq-accordion.md) para outro uso do `Accordion`.
