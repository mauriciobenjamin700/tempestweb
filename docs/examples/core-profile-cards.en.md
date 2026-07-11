# Profile cards — avatar, rating and accordion 🚀

In this example you'll build a **team directory** screen using the core's display
and disclosure components: `Avatar` and `Rating` inside profile `Card` widgets, an
`Accordion` of expandable sections, and `ListTile` rows separated by `Divider`.
Tapping a star records the score; opening an accordion section is state-driven.

---

## What you'll build

- 👤 **Profile cards** with an `Avatar` (initials) and an interactive `Rating`.
- ⭐ A `Rating` that calls `on_rate(stars)` when a star is clicked.
- 📂 An **Accordion** of expandable sections (`open` + `on_toggle`).
- 📋 **ListTile** rows separated by **Divider**.

---

## Prerequisites

```bash
pip install tempestweb
```

!!! tip "Tip"
    If you're not yet familiar with the state → view → patches cycle, read the
    [introductory tutorial](../tutorial/index.md).

---

## Step 1 — The profile and the state

Each member is a mutable `Profile` (the rating changes). The state holds the list
of profiles and the `slug` of the open accordion section (or `None`).

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

!!! note "Note — `slug` as a stable key"
    Each profile has a `slug` that serves both as the widgets' `key` and to locate
    the right profile when recording a rating. Stable keys make the reconciler
    update the correct node.

---

## Step 2 — The profile card with an interactive rating

`Rating` takes `value` (current score), `max_stars` and `on_rate`. The `rate`
handler finds the profile by `slug` and records the new score.

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

## Step 3 — The listing inside the accordion

`ListTile` widgets (with `title` + `subtitle`) separated by `Divider` make up a
section's body.

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

## Step 4 — The state-driven accordion

`Accordion` takes `title`, `open` (a boolean derived from state) and `on_toggle`.
The `toggle` handler opens the clicked section or collapses it if it was already
open.

```python
def toggle(section: str) -> None:
    """Open the given accordion section or collapse it if already open."""

    def apply(state: ProfileCardsState) -> None:
        state.open_section = None if state.open_section == section else section

    app.set_state(apply)
```

!!! info "Info — exclusive accordion with a single field"
    By storing only `open_section: str | None`, we guarantee **at most one**
    section is open at a time. `open=app.state.open_section == "skills"` derives
    each section's state from that single field.

---

## The complete app

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

## Running the example ▶

=== "Mode A — WASM (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/core-profile-cards
    ```

=== "Mode B — Server (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/core-profile-cards
    ```

!!! check "Verification"
    You should see three profile cards with avatars and stars. Click a star → that
    profile's rating updates. Click the "Contact channels" header → the section
    opens and "Shared skills" collapses. ✅

---

## Recap

- ✅ Render profiles with `Avatar` (`initials`/`size`) and an interactive `Rating`.
- ✅ Record the score with `on_rate(stars)`, locating the profile by `slug`.
- ✅ Compose disclosure with an exclusive `Accordion` (`open`/`on_toggle`).
- ✅ List details with `ListTile` + `Divider`.
- ✅ Run the same `app.py` in both modes without changing a line.

!!! tip "Next steps"
    - See [Rating & review](rating-review.md) for more focus on `Rating`.
    - Combine with [FAQ accordion](faq-accordion.md) for another `Accordion` use.
