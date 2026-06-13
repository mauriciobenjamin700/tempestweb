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
