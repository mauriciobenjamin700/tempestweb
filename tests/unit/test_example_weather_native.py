"""Dedicated tests for examples/weather-native/app.py.

Exercises the full async pipeline — geolocation → HTTP weather fetch — using a
fake :class:`NativeBridge`.  Verifies:

* ``build(view(app))`` is green with **no bridge installed** (determinism rule).
* The ``idle`` phase renders a *Get weather* button and no card.
* Driving the ``fetch`` handler transitions: ``idle → loading → loaded``.
* The loaded phase renders a :class:`Card` containing the temperature text.
* A failing geolocation call transitions to the ``error`` phase with a message.
* A failing HTTP call (after a successful locate) also reaches ``error``.
* The ``loading`` phase renders a :class:`Spinner`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempestweb._core import App, Node, build
from tempestweb.native import install_bridge, uninstall_bridge

# ---------------------------------------------------------------------------
# Module loader (mirrors test_examples.py pattern)
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_example(name: str) -> ModuleType:
    """Import an example's ``app`` module by its directory name.

    Args:
        name: The example directory under ``examples/``.

    Returns:
        The imported module exposing ``make_state`` and ``view``.
    """
    module_name = f"_example_{name.replace('-', '_')}"
    path = EXAMPLES_DIR / name / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    """Build an ``App`` around an example module's state and view.

    Args:
        module: An example module exposing ``make_state`` and ``view``.

    Returns:
        An ``App`` whose ``apply_patches`` is a no-op.
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a pre-order list.

    Args:
        node: The root node.

    Returns:
        Every node in the subtree, root first.
    """
    nodes: list[Node] = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def _types(node: Node) -> set[str]:
    """Collect widget type tags present in an IR tree.

    Args:
        node: The root node.

    Returns:
        The set of ``type`` strings found in the subtree.
    """
    return {n.type for n in _walk(node)}


def _find_handler(widget: Any, key: str, attr: str) -> Any:  # noqa: ANN401
    """Find a handler callable on the widget with the given key and attribute.

    Args:
        widget: The root widget returned by ``view``.
        key: The ``key`` of the target widget.
        attr: The handler attribute name (e.g. ``"on_click"``).

    Returns:
        The handler callable.

    Raises:
        AssertionError: If no matching widget is found.
    """
    stack: list[Any] = [widget]
    while stack:
        current = stack.pop()
        if getattr(current, "key", None) == key:
            handler = getattr(current, attr, None)
            if handler is not None:
                return handler
        children = getattr(current, "children", None)
        if children:
            stack.extend(children)
    raise AssertionError(f"no widget with key={key!r} and handler {attr!r}")


# ---------------------------------------------------------------------------
# Fake bridge
# ---------------------------------------------------------------------------


class FakeBridge:
    """Fake native bridge that serves scripted responses for geolocation + HTTP.

    The bridge returns a fixed geolocation fix and a canned Open-Meteo-shaped
    ``current`` block so tests never touch the network.

    Attributes:
        geo_lat: Latitude reported by the fake geolocation.
        geo_lon: Longitude reported by the fake geolocation.
        temperature_c: Temperature (°C) in the fake weather response.
        wind_kmh: Wind speed (km/h) in the fake weather response.
        geo_error: When not ``None``, ``geolocation.get`` raises :class:`NativeError`
            with this code.
        http_error: When not ``None``, ``http.request`` raises :class:`NativeError`
            with this code.
    """

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
        """Initialise the fake bridge with configurable payloads.

        Args:
            geo_lat: Latitude for the geolocation response.
            geo_lon: Longitude for the geolocation response.
            temperature_c: Temperature in the HTTP weather response.
            wind_kmh: Wind speed in the HTTP weather response.
            geo_error: When set, ``geolocation.get`` returns ``ok=False``.
            http_error: When set, ``http.request`` returns ``ok=False``.
        """
        self.geo_lat = geo_lat
        self.geo_lon = geo_lon
        self.temperature_c = temperature_c
        self.wind_kmh = wind_kmh
        self.geo_error = geo_error
        self.http_error = http_error

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch the fake response for the given capability envelope.

        Args:
            envelope: The ``native_call`` envelope with ``capability`` and ``args``.

        Returns:
            A scripted ``{"ok": True, "value": {...}}`` or error response.
        """
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_without_bridge_is_deterministic() -> None:
    """``build(view(app))`` must succeed with no native bridge installed."""
    module = _load_example("weather-native")
    app = _make_app(module)
    node = build(module.view(app))

    assert isinstance(node, Node)
    assert node.type
    assert node.children


def test_idle_phase_has_fetch_button_and_no_card() -> None:
    """The idle phase shows the title, subtitle and fetch button but no Card."""
    module = _load_example("weather-native")
    app = _make_app(module)
    node = build(module.view(app))
    all_nodes = _walk(node)

    keys = {n.key for n in all_nodes}
    assert "title" in keys
    assert "fetch" in keys
    # No weather card or error card in the initial state
    assert "weather-card" not in keys
    assert "error-card" not in keys
    assert "Spinner" not in _types(node)


async def test_fetch_handler_transitions_idle_to_loaded() -> None:
    """Driving the fetch handler with a working fake bridge reaches loaded."""
    module = _load_example("weather-native")
    install_bridge(FakeBridge(temperature_c=18.7, wind_kmh=9.4))
    app = _make_app(module)

    # Idle — no card yet
    idle_node = build(module.view(app))
    assert "weather-card" not in {n.key for n in _walk(idle_node)}

    # Drive the async handler
    handler = _find_handler(module.view(app), "fetch", "on_click")
    await handler()

    assert app.state.phase == module.Phase.LOADED
    assert app.state.weather is not None
    assert app.state.weather.temperature_c == pytest.approx(18.7)
    assert app.state.weather.wind_speed_kmh == pytest.approx(9.4)
    assert app.state.weather.latitude == pytest.approx(-23.5505)

    # Build the loaded view and confirm the Card + temperature text appears
    loaded_node = build(module.view(app))
    all_loaded = _walk(loaded_node)
    keys_loaded = {n.key for n in all_loaded}
    assert "weather-card" in keys_loaded
    assert "temperature" in keys_loaded

    # Temperature text contains the value
    temp_node = next(n for n in all_loaded if n.key == "temperature")
    assert "18.7" in str(temp_node.props.get("content", ""))


async def test_loading_phase_shows_spinner() -> None:
    """While the handler is in flight, the loading phase renders a Spinner."""
    module = _load_example("weather-native")
    app = _make_app(module)

    app.set_state(lambda s: setattr(s, "phase", module.Phase.LOADING))
    loading_node = build(module.view(app))
    assert "Spinner" in _types(loading_node)


async def test_geo_error_transitions_to_error_phase() -> None:
    """A geolocation failure shows the error card with a message."""
    module = _load_example("weather-native")
    install_bridge(FakeBridge(geo_error="permission_denied"))
    app = _make_app(module)

    handler = _find_handler(module.view(app), "fetch", "on_click")
    await handler()

    assert app.state.phase == module.Phase.ERROR
    assert app.state.error  # some message set

    err_node = build(module.view(app))
    keys = {n.key for n in _walk(err_node)}
    assert "error-card" in keys
    assert "error-message" in keys


async def test_http_error_after_successful_geo_transitions_to_error() -> None:
    """An HTTP failure after a successful geolocation fix also reaches error."""
    module = _load_example("weather-native")
    install_bridge(FakeBridge(http_error="network_error"))
    app = _make_app(module)

    handler = _find_handler(module.view(app), "fetch", "on_click")
    await handler()

    assert app.state.phase == module.Phase.ERROR

    err_node = build(module.view(app))
    keys = {n.key for n in _walk(err_node)}
    assert "error-card" in keys


async def test_injected_fakes_bypass_bridge_entirely() -> None:
    """The state accepts injected callables, letting tests avoid FakeBridge."""
    module = _load_example("weather-native")
    # NO bridge installed — injected coroutines are used instead.

    from tempestweb.native.geolocation import Position

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

    handler = _find_handler(module.view(app), "fetch", "on_click")
    await handler()

    assert app.state.phase == module.Phase.LOADED
    assert app.state.weather is not None
    assert app.state.weather.temperature_c == pytest.approx(15.0)
    assert app.state.weather.latitude == pytest.approx(48.85)

    loaded_node = build(module.view(app))
    temp_node = next(n for n in _walk(loaded_node) if n.key == "temperature")
    assert "15.0" in str(temp_node.props.get("content", ""))
