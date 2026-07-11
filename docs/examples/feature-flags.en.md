# Feature Flags — Runtime Feature Toggles 🚀

Learn how to use `FeatureFlagsProvider` and `InMemoryFeatureFlagsAdapter` to
control UI variants at runtime — without touching the transport, without a
network, without any third-party framework.

---

## What you'll build

A feature-flags dashboard with five sections:

- 🏷 **Header** — title and description of the example
- 🟡 **Beta Banner** — beta-channel banner, visible while `beta_banner=True`
- 🖼 **UI Variant** — "New UI" or "Legacy UI" card, swapped by the `new_ui` flag
- 🎛 **Flags Panel** — panel with one row per flag and a toggle button each
- 🔢 **Rebuild Counter** — badge counting how many times any flag was flipped

!!! note "Note — no network, no bridge"
    The example is completely in-process: the `InMemoryFeatureFlagsAdapter`
    stores flags in a Python dict. Swapping it for GrowthBook or LaunchDarkly
    does not change a single line in `view` — only the adapter changes.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading before continuing:

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/feature-flags
touch examples/feature-flags/app.py
```

---

## Step 1 — Defining the state

The state holds the adapter (flag backend), the provider (facade the UI code
uses), and a rebuild counter.

| Field | Type | Meaning |
|---|---|---|
| `adapter` | `InMemoryFeatureFlagsAdapter` | Backend holding the flags dict; exposed so the toggle handler can call `.set()` |
| `flags` | `FeatureFlagsProvider` | Stable facade the `view` uses to read flags via `.is_enabled()` |
| `rebuild_counter` | `int` | Incremented by the change listener to force `set_state` to schedule a rebuild |

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

!!! tip "Tip — why `field(init=False)` for `flags`?"
    `FeatureFlagsProvider` needs the adapter already built so it can subscribe
    to its change stream. Using `field(init=False)` and creating the provider in
    `__post_init__` ensures the adapter exists before the provider is
    instantiated. This keeps the dataclass clean and the wiring automatic.

---

## Step 2 — The colour palette

Define colour constants at the top of the file. This centralises all colour
values and makes the palette readable regardless of which flag is active.

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

## Step 3 — The header

The first widget is a static card with a title and description:

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

## Step 4 — The beta banner

The banner only appears when `beta_banner` is enabled. The visibility logic
lives in `view` (step 8), not in the builder itself:

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

!!! info "Note — conditional rendering in plain Python"
    You don't need any special if/else widget. Use a plain Python `if` in
    `view` to include or omit a widget from the children list. The reconciler
    detects that the node was inserted or removed and generates the correct
    patches automatically.

---

## Step 5 — The UI variants

Two builders, one for each variant of the `new_ui` flag:

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

!!! tip "Tip — unique keys per variant"
    Notice that each variant has `key="new-ui-card"` and `key="legacy-ui-card"`
    respectively. The reconciler uses the `key` to decide whether a node changed
    its type/identity. Distinct keys guarantee that the diff produces a
    `remove + insert` patch (full replacement) instead of trying to update the
    existing node in place.

---

## Step 6 — The flags panel with toggle

The most interesting part: a generic builder for a flag row with its toggle
button. The flip logic calls `adapter.set()` to change the backend value and
then increments `rebuild_counter` via `app.set_state` to prompt the framework
to call `view` again.

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

!!! warning "Warning — order matters in the toggle handler"
    In the `toggle` handler, order is important:

    1. Read the current value with `app.state.flags.is_enabled(flag_key)`
       **before** calling `.set()`.
    2. Call `app.state.adapter.set(flag_key, not current)` to mutate the
       backend.
    3. Call `app.set_state(...)` to increment the counter and schedule a
       rebuild.

    If you swap steps 1 and 2, you'll read the value **after** the mutation and
    flip the flag in the wrong direction.

The full panel builder aggregates two flag rows:

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

## Step 7 — The rebuild counter

A simple badge displaying `rebuild_counter` to confirm the listener is correctly
wired:

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

## Step 8 — Assembling the `view`

The root `view` function composes the sections using plain Python conditionals:

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

!!! check "The central point of the example"
    Notice that `view` uses `app.state.flags.is_enabled("beta_banner")` and
    `app.state.flags.is_enabled("new_ui")` — it **never** accesses the adapter
    directly. This is the correct pattern: the `view` always talks to the
    provider; only the toggle handler talks to the adapter. Replacing the
    adapter with GrowthBook does not change a single line of `view`.

---

## The complete app

Here is the full `examples/feature-flags/app.py`, ready to copy:

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

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/feature-flags
```

Python runs **inside the browser** via Pyodide. No server needed.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/feature-flags
```

Python runs on the server; the browser receives JSON patches over WebSocket and
applies them to the DOM.

!!! check "Verification"
    In either mode you should see:

    1. Header "Feature Flags" with the subtitle describing the adapter
    2. Yellow "Beta" banner (because `beta_banner=True` by default)
    3. Card "Legacy UI — active" (because `new_ui=False` by default)
    4. "Active flags" panel with two rows — `new_ui OFF` and `beta_banner ON`
    5. Badge "Flag changes: 0"
    6. Click **Turn on** in the `new_ui` row → card switches to "New UI — enabled", counter becomes 1
    7. Click **Turn off** in the `new_ui` row → card returns to "Legacy UI — active", counter becomes 2
    8. Click **Turn off** in the `beta_banner` row → yellow banner disappears, counter becomes 3
    9. Click **Turn on** in the `beta_banner` row → banner reappears, counter becomes 4

---

## Automated verification ✅

Run the four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests (9/9 pass)
pytest -q
```

All pass green. The example was written to be `mypy --strict` clean — every
variable and return value is explicitly annotated.

---

## How it works under the hood

### The complete toggle cycle

```
Click "Turn on" (new_ui)
      │
      ▼
toggle() closure
      │
      ├─ app.state.flags.is_enabled("new_ui")  → reads False (before mutation)
      │
      ├─ app.state.adapter.set("new_ui", True)
      │         │
      │         └─ adapter._emit()
      │                 │
      │                 └─ provider._notify()   ← bridge adapter→provider
      │                         │
      │                         └─ provider listeners fire
      │                            (none in this example — counter is the trigger)
      │
      └─ app.set_state(lambda s: s.rebuild_counter + 1)
                │
                ▼
        view(app) called again
                │
                ▼
        app.state.flags.is_enabled("new_ui") → True
                │
                ▼
        sections includes _new_ui_variant(app)
        sections does NOT include _legacy_ui_variant(app)
                │
                ▼
        build(view(app)) produces new IR
                │
                ▼
        diff(before, after) → patches [Remove "legacy-ui-card", Insert "new-ui-card"]
                │
                ▼
        DOM updated
```

### Why is `rebuild_counter` necessary?

`InMemoryFeatureFlagsAdapter` mutates its internal dict when you call `.set()`.
That dict is **not part of the dataclass** `FeatureFlagsState` — it is a nested
object. The framework does not know that the contents of `adapter._flags` changed;
it only schedules a rebuild when `app.set_state` is called with a mutation
visible on the dataclass.

`rebuild_counter` solves this: it is an integer on the dataclass that the
listener increments, making the change visible to the rebuild mechanism. This is
a common technique in reactive frameworks when you need to observe changes in
objects that are external to the main reactive state.

??? note "Technical detail — `on_change` vs `adapter.subscribe`"
    `FeatureFlagsProvider.on_change(listener)` registers a listener that is
    called whenever **any** flag changes. Internally, the provider registered
    itself on the adapter via `adapter.subscribe(self._notify)` in `__init__`,
    and `_notify` fans out to all of the provider's own listeners. This means UI
    code never needs to know about the adapter directly to react to changes — it
    only needs to register with `flags.on_change(...)`.

    In this example we don't use `on_change` explicitly because the toggle calls
    `app.set_state` directly after `.set()`. In a real app with multiple UI
    sections reacting to the same flag, `on_change` would be the right place to
    centralise the rebuild trigger.

### Adapter vs Provider — separation of responsibilities

| | `InMemoryFeatureFlagsAdapter` | `FeatureFlagsProvider` |
|---|---|---|
| Reads flags | `.get(key, default)` | `.get(key, default)`, `.is_enabled(key)` |
| Mutates flags | `.set(key, value)` | — (immutable from the view's perspective) |
| Notifies changes | `.subscribe(listener)` | `.on_change(listener)` |
| Who uses it | Toggle handlers | `view` functions |

This separation is what allows you to swap the backend for GrowthBook or
LaunchDarkly without changing any line of `view`.

---

## Recap

In this tutorial you learned:

- ✅ Create a `FeatureFlagsProvider` wired to an `InMemoryFeatureFlagsAdapter`
- ✅ Use `is_enabled(key)` in `view` for plain-Python conditional rendering
- ✅ Implement the adapter pattern — `view` talks to the provider, the toggle talks to the adapter
- ✅ Use `app.set_state` to force a rebuild when an external object mutates
- ✅ Confirm the wiring via `rebuild_counter` — an observable badge of how many times the view was rebuilt
- ✅ Use `build` + `diff` to verify that patches are non-empty after each toggle

---

## Next steps

Try extending the example:

- 💡 Add a third flag `dark_mode` and use it to swap the colour palette —
  combine with the [Theme Switcher](./theme-switcher.en.md) example
- 💡 Implement a `GrowthBookFeatureFlagsAdapter` using the Python GrowthBook
  client and swap the adapter in `make_state` without changing `view`
- 💡 Register a listener with `flags.on_change(lambda: app.set_state(...))` in
  `__post_init__` and remove the manual `set_state` from the toggle — the result
  will be identical
- 💡 Read [Execution modes](../tutorial/modes.md) to understand how the same
  `app.py` runs on both transports without any changes
