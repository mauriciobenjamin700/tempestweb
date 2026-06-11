# Weather Native — Geolocation + HTTP in a single handler 🌤️

Build a live weather app that chains **two native capabilities** in sequence — GPS geolocation and HTTP request — and learn the canonical async handler pattern for multiple native calls in tempestweb.

---

## What you'll build

A complete app that:

- 📍 Detects your position via `geolocation.get_position` (browser GPS)
- 🌐 Fetches temperature and wind speed from [Open-Meteo](https://open-meteo.com/) via `native.http.request`
- 🔄 Shows a `Spinner` while data is in flight
- 🃏 Displays the data inside a `Card` with a large temperature readout when loaded
- ⚠️ Shows an error `Card` when any step fails
- ✅ Works **identically** in both execution modes (`--mode wasm` and `--mode server`)

!!! note "Note — canonical async handler with multiple capabilities"
    The pipeline `locate → fetch data → update state` is the heart of this example. It demonstrates how to chain two `await` calls to native capabilities inside a single handler, keeping the `idle → loading → loaded/error` phase transition clear and fully testable.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional, but helpful):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` and async handlers work
- [Native capabilities](../capabilities.md) — overview of the `tempestweb.native` module

---

## Creating the project

```bash
mkdir -p examples/weather-native
touch examples/weather-native/app.py
```

---

## Step 1 — Understanding the lifecycle

Before writing any code, visualise what happens when the user clicks **Get weather**:

```
[idle]
  │  user clicks "Get weather"
  ▼
[loading]  ← immediate set_state, before the awaits
  │  await geolocation.get_position()   → Position(lat, lon, accuracy)
  │  await native.http.request(...)     → HttpResponse with Open-Meteo JSON
  ▼
[loaded]   ← WeatherData populated
   or
[error]    ← error message stored
```

This pattern — **mark as `loading` before the awaits, catch exceptions, transition to `error`** — is reusable in any handler with async I/O.

---

## Step 2 — Type aliases and the Open-Meteo helper

Start by defining the types of the two injected capabilities and the function that calls Open-Meteo:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card
from tempestweb._core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import geolocation
from tempestweb.native.geolocation import Position
from tempestweb.native.http import HttpResponse, request

# Coroutine that resolves to a Position; default = real geolocation.get_position.
Locator = Callable[[], Awaitable[Position]]

# Coroutine that accepts a Position and resolves to a weather data dict.
WeatherFetcher = Callable[[Position], Awaitable[dict[str, Any]]]

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def _default_fetch_weather(pos: Position) -> dict[str, Any]:
    """Fetch current weather from Open-Meteo for the given position.

    Args:
        pos: The geographic position to query.

    Returns:
        A dict with at least ``temperature_2m`` (°C) and
        ``wind_speed_10m`` (km/h) keys from the ``current`` block.

    Raises:
        NativeError: If the HTTP call fails at the network level.
        ValueError: If the response JSON is missing the expected keys.
    """
    url = (
        f"{_OPEN_METEO_URL}"
        f"?latitude={pos.latitude}"
        f"&longitude={pos.longitude}"
        "&current=temperature_2m,wind_speed_10m"
        "&timezone=auto"
    )
    resp: HttpResponse = await request("GET", url)
    data: dict[str, Any] = resp.json_body or {}
    current: dict[str, Any] = data.get("current", {})
    if "temperature_2m" not in current:
        raise ValueError(f"unexpected API response: {data!r}")
    return current
```

!!! tip "Tip — why separate `_default_fetch_weather`?"
    Keeping the HTTP call in a module-level function has two benefits: (1) it can be swapped out in tests by injecting a fake callable directly into `WeatherState` without installing any bridge; (2) it is independently testable with a `FakeBridge` that never touches the network.

---

## Step 3 — Application state

Define the lifecycle phases, the data type, and the main state dataclass:

```python
class Phase(StrEnum):
    """Lifecycle phase of the weather fetch pipeline.

    Attributes:
        IDLE: Nothing has been fetched yet.
        LOADING: Geolocation or HTTP fetch is in flight.
        LOADED: Both calls completed; weather data is available.
        ERROR: One of the calls failed; an error message is shown.
    """

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class WeatherData:
    """Decoded weather payload shown in the Card.

    Attributes:
        latitude: The GPS latitude that was used.
        longitude: The GPS longitude that was used.
        temperature_c: Current temperature in degrees Celsius.
        wind_speed_kmh: Current 10 m wind speed in km/h.
    """

    latitude: float
    longitude: float
    temperature_c: float
    wind_speed_kmh: float


@dataclass
class WeatherState:
    """Application state for the weather example.

    Both native capabilities are injected as callable fields so the initial
    ``build(view(app))`` — called with no bridge — never touches the bridge.
    Handlers call the capabilities *inside* ``async def`` closures that only run
    when the user taps a button.

    Attributes:
        phase: The current lifecycle phase.
        weather: Weather data, populated on successful load.
        error: Human-readable error message shown on failure.
        locate: Injected locator capability (default: real geolocation).
        fetch_weather: Injected weather-fetcher capability (default: Open-Meteo).
    """

    phase: Phase = Phase.IDLE
    weather: WeatherData | None = None
    error: str = ""
    locate: Locator = field(default=geolocation.get_position)
    fetch_weather: WeatherFetcher = field(default=_default_fetch_weather)


def make_state() -> WeatherState:
    """Build the initial, idle weather state.

    Returns:
        A fresh :class:`WeatherState` with no data loaded.
    """
    return WeatherState()
```

!!! info "Note — dependency injection via dataclass fields"
    The `locate` and `fetch_weather` fields are **injected callables**. The initial render (`build(view(app))`) never calls them — they are only invoked inside the `async def fetch()` handler, which only runs when the user clicks the button. This ensures `build(view(app))` is **deterministic and bridge-free**.

---

## Step 4 — The chained async handler

This is the heart of the example: a single `async def fetch()` that runs both awaits in sequence:

```python
async def fetch() -> None:
    """Async handler: locate → fetch → update state."""
    app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
    try:
        pos: Position = await app.state.locate()
        current: dict[str, Any] = await app.state.fetch_weather(pos)
    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
        message = str(exc)

        def _on_error(s: WeatherState) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(_on_error)
        return

    data = WeatherData(
        latitude=pos.latitude,
        longitude=pos.longitude,
        temperature_c=float(current.get("temperature_2m", 0.0)),
        wind_speed_kmh=float(current.get("wind_speed_10m", 0.0)),
    )

    def _on_success(s: WeatherState) -> None:
        s.phase = Phase.LOADED
        s.weather = data

    app.set_state(_on_success)
```

Line by line:

| Line | What it does |
|---|---|
| `app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))` | Immediate transition to `loading` before the awaits — Spinner appears |
| `pos = await app.state.locate()` | Awaits the GPS fix (or the fake in tests) |
| `current = await app.state.fetch_weather(pos)` | Awaits the HTTP API call with the position |
| `except Exception` | Any failure at any step goes to `error` |
| `app.set_state(_on_success)` | Final transition to `loaded` with the data |

!!! warning "Native capabilities require a bridge"
    `geolocation.get_position` and `native.http.request` send `native_call` envelopes through the installed bridge. **In a plain Python process (no bridge), calling these functions raises `BrowserUnavailableError`.**

    - **Mode A (WASM):** bootstrap installs an `FFIBridge` that calls `client/native/*.js` directly in the browser via Pyodide FFI — no network hop.
    - **Mode B (server):** the runtime installs a `ProxyBridge` that serialises the call, sends it to the client over WebSocket/SSE, and waits for the `native_result` back.
    - **In tests:** install a `FakeBridge` with `install_bridge(FakeBridge(...))` — or inject callables directly into `WeatherState.locate` and `WeatherState.fetch_weather` to avoid needing any bridge at all.

---

## Step 5 — The `view` function and UI phases

The `view` function picks the correct widget block based on the current phase:

```python
_ACCENT = Color.from_hex("#2563eb")   # blue-600
_ON_SURFACE = Color.from_hex("#0f172a")  # slate-900
_MUTED = Color.from_hex("#64748b")    # slate-500
_ERROR = Color.from_hex("#dc2626")    # red-600


def view(app: App[WeatherState]) -> Widget:
    """Render the weather UI from the current lifecycle phase.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current phase.
    """

    async def fetch() -> None:
        """Async handler: locate → fetch → update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
        try:
            pos: Position = await app.state.locate()
            current: dict[str, Any] = await app.state.fetch_weather(pos)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)

            def _on_error(s: WeatherState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(_on_error)
            return

        data = WeatherData(
            latitude=pos.latitude,
            longitude=pos.longitude,
            temperature_c=float(current.get("temperature_2m", 0.0)),
            wind_speed_kmh=float(current.get("wind_speed_10m", 0.0)),
        )

        def _on_success(s: WeatherState) -> None:
            s.phase = Phase.LOADED
            s.weather = data

        app.set_state(_on_success)

    # ---- header ----
    header = Text(
        content="Weather",
        key="title",
        style=Style(
            font_size=26.0,
            font_weight=FontWeight.BOLD,
            color=_ON_SURFACE,
            text_align=TextAlign.CENTER,
        ),
    )

    subtitle = Text(
        content="Tap the button to detect your location and fetch live weather.",
        key="subtitle",
        style=Style(
            font_size=14.0,
            color=_MUTED,
            text_align=TextAlign.CENTER,
        ),
    )

    fetch_btn = Button(
        label="Get weather",
        on_click=fetch,
        key="fetch",
        style=Style(
            padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
            radius=10.0,
            background=_ACCENT,
        ),
    )

    children: list[Widget] = [header, subtitle, fetch_btn]

    if app.state.phase is Phase.LOADING:
        children.append(
            Column(
                key="loading",
                style=Style(align=AlignItems.CENTER, gap=8.0, padding=Edge.all(16.0)),
                children=[
                    Spinner(key="spinner"),
                    Text(
                        content="Locating you…",
                        key="loading-label",
                        style=Style(font_size=13.0, color=_MUTED),
                    ),
                ],
            )
        )

    elif app.state.phase is Phase.ERROR:
        children.append(
            Card(
                key="error-card",
                children=[
                    Text(
                        content="Something went wrong",
                        key="error-title",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                            color=_ERROR,
                        ),
                    ),
                    Text(
                        content=app.state.error,
                        key="error-message",
                        style=Style(font_size=13.0, color=_MUTED),
                    ),
                ],
            )
        )

    elif app.state.phase is Phase.LOADED and app.state.weather is not None:
        w = app.state.weather
        temp_label = f"{w.temperature_c:.1f} °C"
        wind_label = f"{w.wind_speed_kmh:.1f} km/h wind"
        coords_label = f"{w.latitude:.4f}, {w.longitude:.4f}"

        children.append(
            Card(
                key="weather-card",
                children=[
                    # Large temperature display
                    Text(
                        content=temp_label,
                        key="temperature",
                        style=Style(
                            font_size=52.0,
                            font_weight=FontWeight.BOLD,
                            color=_ACCENT,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                    # Wind speed row
                    Row(
                        key="wind-row",
                        style=Style(
                            gap=6.0,
                            align=AlignItems.CENTER,
                            justify=JustifyContent.CENTER,
                        ),
                        children=[
                            Text(
                                content="Wind",
                                key="wind-label",
                                style=Style(font_size=14.0, color=_MUTED),
                            ),
                            Text(
                                content=wind_label,
                                key="wind-value",
                                style=Style(
                                    font_size=14.0,
                                    font_weight=FontWeight.BOLD,
                                    color=_ON_SURFACE,
                                ),
                            ),
                        ],
                    ),
                    # Coordinates
                    Text(
                        content=coords_label,
                        key="coords",
                        style=Style(
                            font_size=11.0,
                            color=_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            )
        )

    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(20.0),
            align=AlignItems.CENTER,
        ),
        children=children,
    )
```

!!! tip "Tip — mutable `children: list[Widget]`"
    Building a base list `[header, subtitle, fetch_btn]` and then calling `children.append(...)` per phase is an idiomatic tempestweb pattern for conditional rendering without `*([] if ... else [...])`. Either style works — the reconciler treats them identically.

---

## The complete app

Here is the full file, ready to copy:

```python
"""Weather view — headline native example combining geolocation + HTTP.

Demonstrates two native capabilities wired together in a single async handler::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The flow: tap **Get weather** → acquire GPS fix via ``geolocation.get_position`` →
fetch weather data from the Open-Meteo API via ``native.http.request`` → display
temperature, wind speed, and location coordinates inside a :class:`Card`.

Both capabilities are **dependency-injected** into :class:`WeatherState` as
callables with real defaults, so the initial ``build(view(app))`` is deterministic
(no bridge is touched during render), while tests can swap in fakes without
touching global state.

Lifecycle phases follow the same ``idle → loading → loaded/error`` pattern as
:mod:`examples.fetch.app` but now require *two* sequential native calls, which
makes this example the canonical "async handler with multiple capabilities" demo.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card
from tempestweb._core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempestweb._core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import geolocation
from tempestweb.native.geolocation import Position
from tempestweb.native.http import HttpResponse, request

# ---------------------------------------------------------------------------
# Type aliases for the two injected capabilities
# ---------------------------------------------------------------------------

#: Coroutine that resolves to a :class:`Position`.  The default is the real
#: capability; tests inject a fake that returns immediately.
Locator = Callable[[], Awaitable[Position]]

#: Coroutine that accepts a :class:`Position` and resolves to a weather dict.
#: The default calls the Open-Meteo free API; tests inject a scripted dict.
WeatherFetcher = Callable[[Position], Awaitable[dict[str, Any]]]

# ---------------------------------------------------------------------------
# Open-Meteo helper
# ---------------------------------------------------------------------------

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def _default_fetch_weather(pos: Position) -> dict[str, Any]:
    """Fetch current weather from Open-Meteo for the given position.

    Calls the free, no-auth Open-Meteo forecast endpoint and returns the
    ``current`` block of the response JSON.

    Args:
        pos: The geographic position to query.

    Returns:
        A dict with at least ``temperature_2m`` (°C) and
        ``wind_speed_10m`` (km/h) keys from the ``current`` block.

    Raises:
        NativeError: If the HTTP call fails at the network level.
        ValueError: If the response JSON is missing the expected keys.
    """
    url = (
        f"{_OPEN_METEO_URL}"
        f"?latitude={pos.latitude}"
        f"&longitude={pos.longitude}"
        "&current=temperature_2m,wind_speed_10m"
        "&timezone=auto"
    )
    resp: HttpResponse = await request("GET", url)
    data: dict[str, Any] = resp.json_body or {}
    current: dict[str, Any] = data.get("current", {})
    if "temperature_2m" not in current:
        raise ValueError(f"unexpected API response: {data!r}")
    return current


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phase of the weather fetch pipeline.

    Attributes:
        IDLE: Nothing has been fetched yet.
        LOADING: Geolocation or HTTP fetch is in flight.
        LOADED: Both calls completed; weather data is available.
        ERROR: One of the calls failed; an error message is shown.
    """

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class WeatherData:
    """Decoded weather payload shown in the :class:`Card`.

    Attributes:
        latitude: The GPS latitude that was used.
        longitude: The GPS longitude that was used.
        temperature_c: Current temperature in degrees Celsius.
        wind_speed_kmh: Current 10 m wind speed in km/h.
    """

    latitude: float
    longitude: float
    temperature_c: float
    wind_speed_kmh: float


@dataclass
class WeatherState:
    """Application state for the weather example.

    Both native capabilities are injected as callable fields so the initial
    ``build(view(app))`` — called with no bridge — never touches the bridge.
    Handlers call the capabilities *inside* ``async def`` closures that only run
    when the user taps a button.

    Attributes:
        phase: The current lifecycle phase.
        weather: Weather data, populated on successful load.
        error: Human-readable error message shown on failure.
        locate: Injected locator capability (default: real geolocation).
        fetch_weather: Injected weather-fetcher capability (default: Open-Meteo).
    """

    phase: Phase = Phase.IDLE
    weather: WeatherData | None = None
    error: str = ""
    locate: Locator = field(default=geolocation.get_position)
    fetch_weather: WeatherFetcher = field(default=_default_fetch_weather)


def make_state() -> WeatherState:
    """Build the initial, idle weather state.

    Returns:
        A fresh :class:`WeatherState` with no data loaded.
    """
    return WeatherState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

_ACCENT = Color.from_hex("#2563eb")  # blue-600
_ON_SURFACE = Color.from_hex("#0f172a")  # slate-900
_MUTED = Color.from_hex("#64748b")  # slate-500
_ERROR = Color.from_hex("#dc2626")  # red-600


def view(app: App[WeatherState]) -> Widget:
    """Render the weather UI from the current lifecycle phase.

    The async ``fetch`` handler drives the full pipeline:
    ``set_state(loading)`` → ``await locate()`` → ``await fetch_weather(pos)``
    → ``set_state(loaded | error)``.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current phase.
    """

    async def fetch() -> None:
        """Async handler: locate → fetch → update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))
        try:
            pos: Position = await app.state.locate()
            current: dict[str, Any] = await app.state.fetch_weather(pos)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            message = str(exc)

            def _on_error(s: WeatherState) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(_on_error)
            return

        data = WeatherData(
            latitude=pos.latitude,
            longitude=pos.longitude,
            temperature_c=float(current.get("temperature_2m", 0.0)),
            wind_speed_kmh=float(current.get("wind_speed_10m", 0.0)),
        )

        def _on_success(s: WeatherState) -> None:
            s.phase = Phase.LOADED
            s.weather = data

        app.set_state(_on_success)

    # ---- header ----
    header = Text(
        content="Weather",
        key="title",
        style=Style(
            font_size=26.0,
            font_weight=FontWeight.BOLD,
            color=_ON_SURFACE,
            text_align=TextAlign.CENTER,
        ),
    )

    subtitle = Text(
        content="Tap the button to detect your location and fetch live weather.",
        key="subtitle",
        style=Style(
            font_size=14.0,
            color=_MUTED,
            text_align=TextAlign.CENTER,
        ),
    )

    fetch_btn = Button(
        label="Get weather",
        on_click=fetch,
        key="fetch",
        style=Style(
            padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
            radius=10.0,
            background=_ACCENT,
        ),
    )

    children: list[Widget] = [header, subtitle, fetch_btn]

    if app.state.phase is Phase.LOADING:
        children.append(
            Column(
                key="loading",
                style=Style(align=AlignItems.CENTER, gap=8.0, padding=Edge.all(16.0)),
                children=[
                    Spinner(key="spinner"),
                    Text(
                        content="Locating you…",
                        key="loading-label",
                        style=Style(font_size=13.0, color=_MUTED),
                    ),
                ],
            )
        )

    elif app.state.phase is Phase.ERROR:
        children.append(
            Card(
                key="error-card",
                children=[
                    Text(
                        content="Something went wrong",
                        key="error-title",
                        style=Style(
                            font_size=16.0,
                            font_weight=FontWeight.BOLD,
                            color=_ERROR,
                        ),
                    ),
                    Text(
                        content=app.state.error,
                        key="error-message",
                        style=Style(font_size=13.0, color=_MUTED),
                    ),
                ],
            )
        )

    elif app.state.phase is Phase.LOADED and app.state.weather is not None:
        w = app.state.weather
        temp_label = f"{w.temperature_c:.1f} °C"
        wind_label = f"{w.wind_speed_kmh:.1f} km/h wind"
        coords_label = f"{w.latitude:.4f}, {w.longitude:.4f}"

        children.append(
            Card(
                key="weather-card",
                children=[
                    # Large temperature display
                    Text(
                        content=temp_label,
                        key="temperature",
                        style=Style(
                            font_size=52.0,
                            font_weight=FontWeight.BOLD,
                            color=_ACCENT,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                    # Wind speed row
                    Row(
                        key="wind-row",
                        style=Style(
                            gap=6.0,
                            align=AlignItems.CENTER,
                            justify=JustifyContent.CENTER,
                        ),
                        children=[
                            Text(
                                content="Wind",
                                key="wind-label",
                                style=Style(font_size=14.0, color=_MUTED),
                            ),
                            Text(
                                content=wind_label,
                                key="wind-value",
                                style=Style(
                                    font_size=14.0,
                                    font_weight=FontWeight.BOLD,
                                    color=_ON_SURFACE,
                                ),
                            ),
                        ],
                    ),
                    # Coordinates
                    Text(
                        content=coords_label,
                        key="coords",
                        style=Style(
                            font_size=11.0,
                            color=_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            )
        )

    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(20.0),
            align=AlignItems.CENTER,
        ),
        children=children,
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/weather-native/app.py
```

Python runs **inside the browser** via Pyodide. The `FFIBridge` is installed automatically during bootstrap and calls `navigator.geolocation` and `fetch` directly — no Python-to-server network hop.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/weather-native/app.py
```

Python runs on the server; the `ProxyBridge` serialises each `native_call` as a JSON envelope, sends it to the browser over WebSocket, and awaits the `native_result` back. The browser executes `client/native/geolocation.js` and `client/native/http.js` as usual.

!!! check "What you should see"
    In either mode:

    1. Title **Weather** and centred subtitle
    2. Blue **Get weather** button
    3. Click → `Spinner` + "Locating you…" text appear
    4. After GPS + HTTP complete → Card with a large temperature (e.g. `22.5 °C`), wind speed, and coordinates
    5. If you deny location permission → red error Card with the message
    6. Click again → the cycle restarts from the beginning

!!! warning "Geolocation permission"
    The browser will request location permission on first run. If you deny it, `geolocation.get_position` raises `NativeError(code="permission_denied")`, which the handler catches and shows in the error Card. To test the success flow without real GPS, use the fakes described in the next section.

---

## Tests — two fake styles 🧪

### Style 1 — Global `FakeBridge` (covers the whole bridge)

Install a `FakeBridge` before the test and remove it with `uninstall_bridge` afterwards:

```python
import pytest
from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge
from tempestweb.native.geolocation import Position
from typing import Any


class FakeBridge:
    """Fake native bridge that serves scripted responses for geolocation + HTTP."""

    def __init__(
        self,
        *,
        geo_lat: float = -23.5505,
        geo_lon: float = -46.6333,
        temperature_c: float = 22.5,
        wind_kmh: float = 12.3,
        geo_error: str | None = None,
        http_error: str | None = None,
    ) -> None:
        self.geo_lat = geo_lat
        self.geo_lon = geo_lon
        self.temperature_c = temperature_c
        self.wind_kmh = wind_kmh
        self.geo_error = geo_error
        self.http_error = http_error

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        cap: str = envelope.get("capability", "")

        if cap == "geolocation.get":
            if self.geo_error is not None:
                return {"ok": False, "error": self.geo_error, "message": "geo failed"}
            return {
                "ok": True,
                "value": {
                    "latitude": self.geo_lat,
                    "longitude": self.geo_lon,
                    "accuracy": 10.0,
                },
            }

        if cap == "http.request":
            if self.http_error is not None:
                return {"ok": False, "error": self.http_error, "message": "http failed"}
            return {
                "ok": True,
                "value": {
                    "status": 200,
                    "ok": True,
                    "headers": {"content-type": "application/json"},
                    "text": "",
                    "json": {
                        "current": {
                            "temperature_2m": self.temperature_c,
                            "wind_speed_10m": self.wind_kmh,
                        }
                    },
                },
            }

        return {"ok": False, "error": "unavailable", "message": f"no cap: {cap}"}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    """Ensure no bridge leaks between tests."""
    uninstall_bridge()
    yield
    uninstall_bridge()


async def test_fetch_handler_transitions_idle_to_loaded() -> None:
    install_bridge(FakeBridge(temperature_c=18.7, wind_kmh=9.4))
    # ... rest of the test
```

### Style 2 — Injected callables (no bridge at all)

You can swap out only `locate` and `fetch_weather` directly on the state, without needing any global bridge:

```python
import pytest
from tempestweb._core import App
from tempestweb.native.geolocation import Position
from typing import Any


async def test_injected_fakes_bypass_bridge_entirely() -> None:
    """The state accepts injected callables, letting tests avoid FakeBridge."""
    # Import the example module
    import importlib.util, sys
    from pathlib import Path

    path = Path("examples/weather-native/app.py")
    spec = importlib.util.spec_from_file_location("_weather", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_weather"] = module
    spec.loader.exec_module(module)

    # NO bridge installed — inject coroutines directly
    async def fake_locate() -> Position:
        return Position(latitude=48.85, longitude=2.35, accuracy=5.0)

    async def fake_weather(_pos: Position) -> dict[str, Any]:
        return {"temperature_2m": 15.0, "wind_speed_10m": 7.0}

    state = module.make_state()
    state.locate = fake_locate
    state.fetch_weather = fake_weather

    app: App[Any] = App(
        state=state, view=module.view, apply_patches=lambda _patches: None
    )

    # Find and run the handler
    widget = module.view(app)
    stack = [widget]
    handler = None
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == "fetch":
            handler = getattr(current, "on_click", None)
            break
        stack.extend(getattr(current, "children", []))

    await handler()

    assert app.state.phase == module.Phase.LOADED
    assert app.state.weather.temperature_c == pytest.approx(15.0)
    assert app.state.weather.latitude == pytest.approx(48.85)
```

!!! tip "Tip — which style to choose?"
    Use **`FakeBridge`** when you want to test the full dispatch integration (envelopes, `ok`/`error` responses, multiple capabilities). Use **injected callables** for unit tests focused on state logic — they are faster to write and more explicit about what is being tested.

---

## Automated verification ✅

Run all four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests (includes the 7 tests for this example)
pytest -q tests/unit/test_example_weather_native.py
```

The 7 tests cover:

| Test | What it verifies |
|---|---|
| `test_build_without_bridge_is_deterministic` | `build(view(app))` works with no bridge installed |
| `test_idle_phase_has_fetch_button_and_no_card` | `idle` phase has the `fetch` button and no `Card` |
| `test_fetch_handler_transitions_idle_to_loaded` | `FakeBridge` drives `idle` → `loaded` with correct data |
| `test_loading_phase_shows_spinner` | `loading` phase renders a `Spinner` |
| `test_geo_error_transitions_to_error_phase` | Geolocation error → `error` phase + error Card |
| `test_http_error_after_successful_geo_transitions_to_error` | HTTP error after successful GPS → `error` phase |
| `test_injected_fakes_bypass_bridge_entirely` | Injected callables work without any bridge |

---

## How it works under the hood 🔬

### The update cycle with native capabilities

```
Click "Get weather"
        │
        ▼
async def fetch()  ← handler inside view()
        │
        ├─► app.set_state(LOADING)   ← immediate re-render → Spinner appears
        │
        ├─► await app.state.locate() ─────────────────────────────────┐
        │                                                              │
        │       [Mode A]  FFIBridge → client/native/geolocation.js    │
        │       [Mode B]  ProxyBridge → WS → browser → WS back        │
        │                                                              │
        │◄──────────────────────────── Position(lat, lon, accuracy) ◄─┘
        │
        ├─► await app.state.fetch_weather(pos) ───────────────────────┐
        │                                                              │
        │       [Mode A]  FFIBridge → client/native/http.js           │
        │       [Mode B]  ProxyBridge → WS → browser fetch → back     │
        │                                                              │
        │◄──────────────────────────── {"temperature_2m": ..., ...} ◄─┘
        │
        ├─► app.set_state(LOADED)    ← re-render → Card appears
        │
        └─► (or app.set_state(ERROR) if any await raised)
```

### Why is the initial render deterministic?

`WeatherState.locate` and `WeatherState.fetch_weather` are dataclass fields with defaults (`geolocation.get_position` and `_default_fetch_weather`). The `view()` function **only references them inside closures within `async def fetch()`**. The initial render never calls `fetch()` — it merely creates the `Button` widget with `on_click=fetch`. That is why `build(view(app))` succeeds even with no bridge installed.

### `install_bridge` and `uninstall_bridge`

```python
from tempestweb.native import install_bridge, uninstall_bridge

# Mode A bootstrap (done by the runtime, not the app code):
install_bridge(FFIBridge(dispatch=window.__tempestweb_native__))

# Mode B bootstrap (done by the runtime):
install_bridge(ProxyBridge(send_frame=ws_session.send))

# Session teardown / test cleanup:
uninstall_bridge()
```

The bridge is a process-wide singleton. `install_bridge` replaces any previous bridge. `uninstall_bridge` removes the bridge, restoring the "off-platform" state — any native call after this point raises `BrowserUnavailableError`.

---

## Recap

In this tutorial you learned:

- ✅ Chain **two native capabilities** (`geolocation` + `http`) in a single `async def` handler
- ✅ Use the `idle → loading → loaded/error` pattern with `set_state` before and after awaits
- ✅ Keep `build(view(app))` **deterministic** by injecting capabilities as dataclass fields
- ✅ Use `FakeBridge` to test the full dispatch pipeline without network access
- ✅ Use **injected callables** as a lighter-weight alternative to `FakeBridge`
- ✅ Understand the role of `install_bridge` / `uninstall_bridge` in both execution modes
- ✅ Use `Card` as a result container and `Spinner` as a loading indicator

---

## Next steps

Try extending the example:

- 💡 Add a **Refresh** button that only appears in the `loaded` phase and restarts the cycle
- 💡 Show a weather condition icon (sunny, cloudy) using additional Open-Meteo data (`weathercode`)
- 💡 Explore [native capabilities](../capabilities.md) to see `audio`, `camera`, `share`, and `notifications`
- 💡 Add automatic retry on HTTP failures with `RetryOptions` — already built into `native.http.request`
- 💡 Read the [wire contract](../wire-contract.md) to understand the full `native_call` / `native_result` envelope
