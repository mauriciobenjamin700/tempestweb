"""Core profile cards — showcasing display & disclosure components.

This example renders a small team-directory screen built entirely from the
core's display/disclosure components: :class:`Avatar` and :class:`Rating`
inside profile :class:`Card` widgets, an :class:`Accordion` of expandable
detail sections, and :class:`ListTile` rows separated by :class:`Divider`.

The same ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

Interaction is wired through state: toggling a section header calls
``Accordion.on_toggle`` to open or close it. The ``Rating`` is display-only (a
clickable Rating lowers to filled star Buttons that the web base theme paints as
solid pills — see the note at its call site).
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
        rating: Star score (0..5) shown by the display-only ``Rating``.
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


def _profile_card(profile: Profile) -> Widget:
    """Render one profile card with an avatar and a display rating.

    Args:
        profile: The team member to render.

    Returns:
        A :class:`Card` widget for the given profile.
    """

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
            # Display-only Rating: the core lowers a *clickable* Rating to filled
            # Buttons (one per star), which the web's Material 3 base paints as
            # solid pills over the star glyph. A display Rating renders the
            # ★/☆ glyphs cleanly; click-to-rate awaits a borderless star variant.
            Rating(
                key=f"rating-{profile.slug}",
                value=profile.rating,
                max_stars=5,
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
            *[_profile_card(profile) for profile in app.state.profiles],
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
