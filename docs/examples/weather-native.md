# Weather Native — Geolocalização + HTTP em um único handler 🌤️

Construa um app de previsão do tempo que combina **duas capacidades nativas** em sequência — geolocalização do GPS e requisição HTTP — e aprenda o padrão canônico de handler assíncrono com múltiplas chamadas nativas no tempestweb.

---

## O que você vai construir

Um app completo que:

- 📍 Detecta a sua posição via `geolocation.get_position` (GPS do browser)
- 🌐 Busca a temperatura e velocidade do vento na [Open-Meteo](https://open-meteo.com/) via `native.http.request`
- 🔄 Exibe um `Spinner` enquanto os dados chegam
- 🃏 Mostra os dados dentro de um `Card` com temperatura em destaque quando carregado
- ⚠️ Exibe um `Card` de erro quando qualquer etapa falha
- ✅ Funciona **idêntico** nos dois modos de execução (`--mode wasm` e `--mode server`)

!!! note "Nota — exemplo canônico de handler assíncrono com múltiplas capacidades"
    O pipeline `localizar → buscar dados → atualizar estado` é o coração deste exemplo. Ele demonstra como encadear dois `await` de capacidades nativas dentro de um único handler, mantendo a transição de fases `idle → loading → loaded/error` clara e testável.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada (opcional, mas útil):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` e handlers assíncronos funcionam
- [Capacidades nativas](../capabilities.md) — visão geral do módulo `tempestweb.native`

---

## Criando o projeto

```bash
mkdir -p examples/weather-native
touch examples/weather-native/app.py
```

---

## Passo 1 — Entendendo o ciclo de vida

Antes de escrever código, visualize o que vai acontecer quando o usuário clicar em **Get weather**:

```
[idle]
  │  usuário clica em "Get weather"
  ▼
[loading]  ← set_state imediato, antes dos awaits
  │  await geolocation.get_position()   → Position(lat, lon, accuracy)
  │  await native.http.request(...)     → HttpResponse com JSON do Open-Meteo
  ▼
[loaded]   ← WeatherData populado
   ou
[error]    ← mensagem de erro armazenada
```

Esse padrão — **marcar como `loading` antes dos awaits, capturar exceções e transicionar para `error`** — é reutilizável em qualquer handler com I/O assíncrono.

---

## Passo 2 — Tipos de aliases e o helper Open-Meteo

Começamos definindo os tipos das duas capacidades injetadas e a função que chama a Open-Meteo:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.components import Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import geolocation
from tempestweb.native.geolocation import Position
from tempestweb.native.http import HttpResponse, request

# Coroutine que resolve para um Position; padrão = geolocation.get_position real.
Locator = Callable[[], Awaitable[Position]]

# Coroutine que aceita um Position e resolve para um dict de dados meteorológicos.
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

!!! tip "Dica — por que separar `_default_fetch_weather`?"
    Manter a chamada HTTP em uma função de nível de módulo tem duas vantagens: (1) ela pode ser substituída nos testes por uma função fake sem precisar instalar nenhum bridge; (2) ela é testável de forma independente com um `FakeBridge` que não acessa a rede.

---

## Passo 3 — Estado da aplicação

Agora definimos as fases do ciclo de vida, o tipo de dado e o estado principal:

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

!!! info "Nota — injeção de dependência via campos de dataclass"
    Os campos `locate` e `fetch_weather` são **callables injetados**. A render inicial (`build(view(app))`) nunca os chama — eles só são invocados dentro do handler `async def fetch()`, que só executa quando o usuário clica no botão. Isso garante que `build(view(app))` seja **determinístico e sem bridge instalado**.

---

## Passo 4 — O handler assíncrono encadeado

Este é o coração do exemplo: um único `async def fetch()` que executa os dois awaits em sequência:

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

Veja o que acontece linha a linha:

| Linha | O que faz |
|---|---|
| `app.set_state(lambda s: setattr(s, "phase", Phase.LOADING))` | Transição imediata para `loading` antes dos awaits — o Spinner aparece |
| `pos = await app.state.locate()` | Aguarda o GPS (ou o fake nos testes) |
| `current = await app.state.fetch_weather(pos)` | Aguarda a API HTTP passando a posição |
| `except Exception` | Qualquer falha em qualquer etapa vai para `error` |
| `app.set_state(_on_success)` | Transição final para `loaded` com os dados |

!!! warning "Atenção — capacidades nativas precisam de um bridge"
    `geolocation.get_position` e `native.http.request` enviam envelopes `native_call` através do bridge instalado. **Em um processo Python puro (sem bridge), chamar essas funções levanta `BrowserUnavailableError`.**

    - **Modo A (WASM):** o bootstrap instala um `FFIBridge` que chama `client/native/*.js` diretamente no browser via Pyodide FFI — sem hop de rede.
    - **Modo B (servidor):** o runtime instala um `ProxyBridge` que serializa a chamada, envia ao cliente pelo WebSocket/SSE, e aguarda o `native_result` de volta.
    - **Nos testes:** instale um `FakeBridge` com `install_bridge(FakeBridge(...))` — ou injete callables diretamente em `WeatherState.locate` e `WeatherState.fetch_weather` para não precisar de bridge nenhum.

---

## Passo 5 — A função `view` e as fases da UI

A função `view` seleciona o bloco de widgets correto baseado na fase atual:

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

!!! tip "Dica — `children: list[Widget]` mutável"
    Construir a lista base `[header, subtitle, fetch_btn]` e depois fazer `children.append(...)` conforme a fase é um padrão idiomático no tempestweb para renderização condicional sem `*([] if ... else [...])`. Use qualquer um dos dois — o reconciliador trata ambos da mesma forma.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Weather view — headline native example combining geolocation + HTTP.

Demonstrates two native capabilities wired together in a single async handler::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

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

from tempest_core import App, Style, Widget
from tempest_core.components import Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Button, Column, Row, Spinner, Text
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

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/weather-native
```

Python roda **dentro do browser** via Pyodide. O `FFIBridge` é instalado automaticamente durante o bootstrap e chama `navigator.geolocation` e `fetch` diretamente — sem hop de rede do Python para o servidor.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/weather-native
```

Python roda no servidor; o `ProxyBridge` serializa cada `native_call` como um envelope JSON, envia ao browser pelo WebSocket, e aguarda o `native_result` de volta. O browser executa `client/native/geolocation.js` e `client/native/http.js` como sempre.

!!! check "O que você deve ver"
    Em qualquer modo:

    1. Título **Weather** e subtítulo centralizado
    2. Botão azul **Get weather**
    3. Clique → `Spinner` + texto "Locating you…" aparecem
    4. Após GPS + HTTP concluírem → Card com temperatura grande (ex.: `22.5 °C`), velocidade do vento e coordenadas
    5. Se você negar permissão de localização → Card vermelho de erro com a mensagem
    6. Clique novamente → repete o ciclo do início

!!! warning "Permissão de geolocalização"
    O browser pedirá permissão de localização na primeira execução. Se você negar, o `geolocation.get_position` levanta `NativeError(code="permission_denied")`, que o handler captura e exibe no Card de erro. Para testar o fluxo de sucesso sem GPS real, use os fakes descritos na próxima seção.

---

## Testes — dois estilos de fake 🧪

### Estilo 1 — `FakeBridge` global (cobre o bridge inteiro)

Instale um `FakeBridge` antes do teste e remova depois com `uninstall_bridge`:

```python
import pytest
from tempest_core import App, Node, build
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
    # ... restante do teste
```

### Estilo 2 — callables injetados (sem bridge nenhum)

Você pode substituir apenas `locate` e `fetch_weather` diretamente no estado, sem precisar de um bridge global:

```python
import pytest
from tempest_core import App
from tempestweb.native.geolocation import Position
from typing import Any


async def test_injected_fakes_bypass_bridge_entirely() -> None:
    """The state accepts injected callables, letting tests avoid FakeBridge."""
    # Importe o módulo de exemplo
    import importlib.util, sys
    from pathlib import Path

    path = Path("examples/weather-native/app.py")
    spec = importlib.util.spec_from_file_location("_weather", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_weather"] = module
    spec.loader.exec_module(module)

    # SEM bridge instalado — injeta coroutines diretamente
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

    # Encontra e executa o handler
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

!!! tip "Dica — qual estilo escolher?"
    Use o **`FakeBridge`** quando quiser testar a integração completa do dispatch (envelopes, respostas `ok`/`error`, múltiplas capacidades). Use os **callables injetados** para testes unitários focados na lógica de estado — eles são mais rápidos de escrever e mais explícitos sobre o que está sendo testado.

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

# Testes (inclui os 7 testes deste exemplo)
pytest -q tests/unit/test_example_weather_native.py
```

Os 7 testes cobrem:

| Teste | O que verifica |
|---|---|
| `test_build_without_bridge_is_deterministic` | `build(view(app))` funciona sem bridge instalado |
| `test_idle_phase_has_fetch_button_and_no_card` | Fase `idle` tem botão `fetch` e nenhum `Card` |
| `test_fetch_handler_transitions_idle_to_loaded` | `FakeBridge` leva de `idle` para `loaded` com dados corretos |
| `test_loading_phase_shows_spinner` | Fase `loading` renderiza `Spinner` |
| `test_geo_error_transitions_to_error_phase` | Erro de geolocalização → fase `error` + Card de erro |
| `test_http_error_after_successful_geo_transitions_to_error` | Erro HTTP após GPS OK → fase `error` |
| `test_injected_fakes_bypass_bridge_entirely` | Callables injetados dispensam o bridge |

---

## Como funciona por dentro 🔬

### O ciclo de update com capacidades nativas

```
Clique em "Get weather"
        │
        ▼
async def fetch()  ← handler dentro de view()
        │
        ├─► app.set_state(LOADING)   ← re-render imediato → Spinner aparece
        │
        ├─► await app.state.locate() ─────────────────────────────────┐
        │                                                              │
        │          [Modo A]  FFIBridge → client/native/geolocation.js │
        │          [Modo B]  ProxyBridge → WS → browser → WS back     │
        │                                                              │
        │◄──────────────────────────── Position(lat, lon, accuracy) ◄─┘
        │
        ├─► await app.state.fetch_weather(pos) ───────────────────────┐
        │                                                              │
        │          [Modo A]  FFIBridge → client/native/http.js        │
        │          [Modo B]  ProxyBridge → WS → browser fetch → back  │
        │                                                              │
        │◄──────────────────────────── {"temperature_2m": ..., ...} ◄─┘
        │
        ├─► app.set_state(LOADED)    ← re-render → Card aparece
        │
        └─► (ou app.set_state(ERROR) se qualquer await levantou)
```

### Por que a render inicial é determinística?

`WeatherState.locate` e `WeatherState.fetch_weather` são campos do dataclass com padrões (`geolocation.get_position` e `_default_fetch_weather`). A função `view()` **só os referencia por closures dentro de `async def fetch()`**. A render inicial nunca chama `fetch()` — ela apenas cria o widget `Button` com `on_click=fetch`. Por isso `build(view(app))` funciona mesmo sem bridge instalado.

### `install_bridge` e `uninstall_bridge`

```python
from tempestweb.native import install_bridge, uninstall_bridge

# Bootstrap do Modo A (feito pelo runtime, não pelo código do app):
install_bridge(FFIBridge(dispatch=window.__tempestweb_native__))

# Bootstrap do Modo B (feito pelo runtime):
install_bridge(ProxyBridge(send_frame=ws_session.send))

# Teardown de sessão / limpeza de teste:
uninstall_bridge()
```

O bridge é um singleton de processo. `install_bridge` substitui qualquer bridge anterior. `uninstall_bridge` remove o bridge, restaurando o estado "sem plataforma" — qualquer chamada nativa após isso levantará `BrowserUnavailableError`.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Encadear **duas capacidades nativas** (`geolocation` + `http`) em um único handler `async def`
- ✅ Usar o padrão `idle → loading → loaded/error` com `set_state` antes e depois dos awaits
- ✅ Manter `build(view(app))` **determinístico** injetando capacidades como campos de dataclass
- ✅ Usar `FakeBridge` para testar o pipeline completo de dispatch sem acesso à rede
- ✅ Usar **callables injetados** como alternativa mais leve ao `FakeBridge`
- ✅ Entender o papel de `install_bridge` / `uninstall_bridge` nos dois modos de execução
- ✅ Usar `Card` como container de resultado e `Spinner` como indicador de carregamento

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um botão **Refresh** que só aparece na fase `loaded` e repete o ciclo
- 💡 Mostre o ícone de condição do tempo (ensolarado, nublado) usando dados adicionais da Open-Meteo (`weathercode`)
- 💡 Explore [capacidades nativas](../capabilities.md) para ver `audio`, `camera`, `share` e `notifications`
- 💡 Adicione retry automático em falhas HTTP com `RetryOptions` — já embutido em `native.http.request`
- 💡 Leia [wire contract](../wire-contract.md) para entender o envelope `native_call` / `native_result` completo
