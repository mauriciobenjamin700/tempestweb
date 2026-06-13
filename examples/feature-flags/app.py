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
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.style import Border, Color, Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Container, Row, Text
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
        A :class:`~tempestweb._core.widgets.Column` with title and subtitle
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
        A :class:`~tempestweb._core.widgets.Row` with flag info and a button.
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
        A :class:`~tempestweb._core.widgets.Text` displaying the counter.
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
