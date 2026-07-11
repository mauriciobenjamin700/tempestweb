# tempestweb

📚 **Documentation:** [Português (Brasil)](https://mauriciobenjamin700.github.io/tempestweb/)
· [English (US)](https://mauriciobenjamin700.github.io/tempestweb/en/) — bilingual
docs site (PT-BR default + EN-US), deployed to GitHub Pages.

> Build web apps in **typed Python**. One declarative widget tree, a **DOM**
> renderer, and **three execution modes** that share 100% of the application code:
> **Mode A (WASM)** runs your Python in the browser via Pyodide; **Mode B
> (server)** runs it on the server (FastAPI) and talks to a thin JS client over
> **WebSocket or SSE**; **Mode C (transpile)** transcribes your
> Python to **native JavaScript** — zero Python runtime, static hosting, great
> first-paint/SEO. Installable **PWA**, **offline-first** (service worker +
> IndexedDB), and **WebPush** are first-class — parity with `tempest-react-sdk`.

Sister project to [tempestroid](../tempestroid) — same "one tree, multiple
renderers" architecture. The renderer-agnostic engine (IR, reconciler, state,
style, widgets) is shared; tempestweb adds a **DOM** leaf renderer (pure
JavaScript, no framework, no build step, no TypeScript) and two patch transports.

## Status

Published on PyPI and functional across all three modes — a working counter runs
live under WASM, server, and transpile; the full test gate is green and every
example builds. The transpile mode (C) is now a **mature, first-class mode** —
100% of `tempest_core` widgets, a wide typed-Python subset, and a full PWA story
(installable, offline, WebPush). Only a handful of advanced constructs sit outside
its subset, and the compiler fails early with `file:line` when you hit one. Design
docs:

- [`docs/plan.md`](docs/plan.md) — full design and phase plan.
- [`docs/roadmap.md`](docs/roadmap.md) — phase checklist.
- [`docs/arquitetura.md`](docs/arquitetura.md) — architecture.
- [`docs/contract.md`](docs/contract.md) — the Python↔client wire format.
- [`docs/agents/MANIFEST.md`](docs/agents/MANIFEST.md) — parallel agent task plan.

Want runnable apps? Browse the **[Example Gallery](https://mauriciobenjamin700.github.io/tempestweb/en/examples/)**
([PT-BR](https://mauriciobenjamin700.github.io/tempestweb/examples/)) — 50+
single-concept demos (stopwatch, forms, data table/grid, kanban, chat, theming,
i18n, canvas charts, app shells, native capabilities, observability, PWA/WebPush,
a Mode C tour, and a server-mode walkthrough), each running unchanged across the
execution modes.

Building something real? Read the **[App architecture & best practices](https://mauriciobenjamin700.github.io/tempestweb/best-practices/)**
guide ([EN](https://mauriciobenjamin700.github.io/tempestweb/en/best-practices/)) —
the ideal layered structure (routes · pages · components · styles · controllers ·
services · storages · schemas · utils · core), mirroring `tempest-fastapi-sdk`, so
your app doesn't rot into garbage code.

## Get started

```bash
pip install "tempestweb[server,cli]"   # or: uv add "tempestweb[server,cli]"

tempestweb new myapp                   # scaffold app.py + tempestweb.toml
cd myapp
tempestweb dev                         # http://127.0.0.1:8000, hot-reload (wasm)
```

The scaffold's `app.py` exposes the two callables every project needs —
`make_state()` and `view(app)` — and `tempestweb.toml` names the entrypoint
(`app.py` by default, configurable). Then pick a mode at build/run time, never in
the app:

```bash
tempestweb build --mode wasm       --path myapp   # static Pyodide bundle
tempestweb run   --mode server     --path myapp   # Mode B: FastAPI + WebSocket
tempestweb build --mode transpile  --path myapp   # native JS, CDN-servable
```

> `dev` serves the static modes (`wasm`/`transpile`); **Mode B (server)** is served
> by `run --mode server`. Every command takes the project **directory** via
> `--path` (default: cwd) — not a positional `.py` file.

Full walkthrough: the [Installation](https://mauriciobenjamin700.github.io/tempestweb/en/installation/)
and [Tutorial](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/) guides.

## How it works

```text
   view(app) ──build──▶ Node tree (IR) ──diff──▶ [ Patch ]   ← shared core (tempest-core)
                                                    │          insert/remove/update/reorder/replace
              ╭─────────────────┬───────────────────┤
       Mode A transport   Mode B transport     Mode C: transpile view() → native JS;
       (pyodide.ffi)      (WebSocket | SSE)     the core runs IN JS, patches in-process
              ╰─────────────────┴───────────────────╯
                  client/ (pure JS): apply patches to the DOM
                  + Style→CSS + event capture          ← same client code in every mode
```

The application's `view()` never names a transport — the same
`examples/counter/app.py` runs under `--mode wasm`, `--mode server` and
`--mode transpile` unchanged. Capabilities (`native/`) are typed awaitables with
the same Python API in every mode — Mode A calls the Web API in-process, Mode B
proxies it over a round-trip, Mode C routes to the same JS glue via an in-process
facade (see [`docs/contract.md`](docs/contract.md)). Track T brings **web-platform
parity**: beyond the core (http, audio, share, geolocation, clipboard, storage,
camera, install, offline, notifications), the bridge now covers **Tier 1** (
vibration, badge, wakelock, fullscreen, network, visibility, orientation, quota,
rich clipboard, battery, sensors), **Tier 2** (speech, recorder, filesystem,
bgsync, tabs, idle), and **Tier 3 / Chromium-only** (bluetooth, usb, serial, hid,
nfc, contacts, payment, pip, eyedropper, pointerlock, gamepad, midi, webaudio).
A **native event channel** streams continuous capabilities (geolocation/network/
battery watch, sensors, STT, …) as typed `async for` iterators. See the
[capability reference](https://mauriciobenjamin700.github.io/tempestweb/native-reference/)
([EN](https://mauriciobenjamin700.github.io/tempestweb/en/native-reference/)) and
the [event-channel guide](https://mauriciobenjamin700.github.io/tempestweb/native-events/).

## Static SSR — `render_to_html`

Another render target, alongside the interactive modes: the **same** typed tree
renders to a **static HTML string** on the server — no JavaScript, no DOM, no
runtime. HTML is just another leaf renderer.

```python
from tempest_core import Column, Text, Button, Style
from tempest_core.style import Edge
from tempestweb.html import render_to_html, render_document

tree: Column = Column(
    style=Style(gap=8.0, padding=Edge.all(16)),
    children=[Text(content="Hello"), Button(label="Click")],
)

fragment: str = render_to_html(tree)                 # an HTML fragment
page: str = render_document(tree, title="Home", htmx=True)  # a full document
```

The CSS is **byte-identical** to what the DOM client emits (the `style_to_css`
port mirrors `client/style.js`), and the new `tempest-core` 0.9.0 `Widget.tag` /
`Widget.attrs` fields let you emit semantic, htmx-ready markup
(`Container(tag="nav", attrs={"hx-get": "/x"})`). All text/attributes are escaped.
See the [Static SSR guide](https://mauriciobenjamin700.github.io/tempestweb/ssr/)
([EN](https://mauriciobenjamin700.github.io/tempestweb/en/ssr/)).

## Mode C — transpile to native JS 🚀

The "TypeScript story" for Python: you write the typed-Python app; a compiler
transcribes the **app layer** (state, `view()`, handlers) to **native
JavaScript**, reusing the whole shared JS renderer. **Zero Python runtime** in the
browser — static hosting, small bundle, great first-paint/SEO.

```python
# examples/counter/app.py  (unchanged from Modes A/B)
@dataclass
class CounterState:
    value: int = 0

def view(app: App[CounterState]) -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))
    return Column(children=[
        Text(content=f"Count: {app.state.value}", key="label"),
        Button(label="+", on_click=increment, key="inc"),
    ])
```

```python
from tempestweb.transpile import transpile_file

js: str = transpile_file("examples/counter/app.py")  # -> native ES module
```

The generated module runs on the native runtime (`client/transpile/runtime.js`)
with a JS `diff` locked against a core-derived golden. Coverage is now **100% of
`tempest_core`**: all ~64 widgets, MD3 styling, state-with-methods, navigation
(routes + URL), i18n, theme + responsiveness, native capabilities (http/storage/
cookies/…), field validators and both declarative and imperative animation. The
`tempestweb build/dev --mode transpile` CLI emits a static, CDN-servable bundle
that is a **first-class PWA — installable and offline out of the box** (manifest
+ cache-first service worker precaching the whole shell; customize via `[pwa]` in
`tempestweb.toml`).

See the canonical [`examples/transpile-tour`](examples/transpile-tour/app.py) —
one app exercising the whole surface — and the guide
([PT](https://mauriciobenjamin700.github.io/tempestweb/transpile/) ·
[EN](https://mauriciobenjamin700.github.io/tempestweb/en/transpile/)). It is a
**first-class mode**: only a handful of advanced constructs sit outside the typed
subset (out-of-subset constructs fail loud with `file:line`).

## Scaffold a PWA

```bash
tempestweb new myapp --template pwa    # Mode C: installable, offline PWA
tempestweb build --mode transpile --path myapp
```

The `pwa` template pre-configures `mode = "transpile"` + a `[pwa]` manifest block
and ships a counter with an **Install** button. Omit `--template` for the plain
counter starter that runs unchanged in all three modes.

## WebPush (end-to-end)

Push works client-to-server out of the box. Generate VAPID keys, mount the
router, subscribe from the client:

```bash
tempestweb vapid --env        # -> VAPID_PUBLIC_KEY=… / VAPID_PRIVATE_KEY=…
```

```python
from fastapi import FastAPI
from tempestweb.server import VapidConfig, WebPushService, webpush_router

service = WebPushService(VapidConfig.from_env())
app = FastAPI()
app.include_router(webpush_router(service))   # /webpush/{subscribe,unsubscribe,send}
```

The client subscribes with `native.notifications.subscribe(public_key)` and POSTs
the subscription to `/webpush/subscribe`; `POST /webpush/send` pushes to it. See
the runnable [`examples/webpush-server`](examples/webpush-server/server.py).

## Deploy (server mode)

```bash
tempestweb deploy --server-name app.example.com --tls    # -> deploy/
cd deploy && docker compose up --build
```

Generates a tailored `nginx.conf` (WebSocket upgrade, streaming timeouts, sticky
`ip_hash`, optional TLS), a `Dockerfile`, `docker-compose.yml` and a `DEPLOY.md`.
Harden the app with a `SecurityConfig` (auth, CORS, limits, rate limiting,
headers) — see the [Security](https://mauriciobenjamin700.github.io/tempestweb/en/security/)
and [Deploy](https://mauriciobenjamin700.github.io/tempestweb/en/deploy/) guides.
Static modes (A/C) need no server — publish the build to any CDN.

## Develop

```bash
uv venv && uv pip install -e ".[dev,server,cli]"
make check          # ruff + mypy + pytest + JS (jsdom) tests
```

## Layout

| Path | What |
|---|---|
| `tempest-core` (dependency) | Renderer-agnostic engine — IR/reconciler/state/style/widgets (`import tempest_core`), extracted from tempestroid. |
| `tempestweb/components/` | Native fields + forms (EmailField, PasswordField, LoginForm, …) plus the re-exported tempest-core library — 54 Material 3 components (Card, DataTable, Tabs, Drawer, Alert, BarChart/LineChart, …). |
| `tempestweb/transports/` | The one seam between modes (`base.py` Protocol, `wasm.py`, `websocket.py`, `sse.py`). |
| `tempestweb/html/` | Static SSR leaf renderer — `render_to_html` / `render_document` / `style_to_css` (Python port of `client/style.js`). |
| `tempestweb/transpile/` | **Mode C:** `ast`-based Python→JS compiler for the app layer. Paired with the native runtime in `client/transpile/` (`diff.js` · `widgets.js` · `runtime.js`). |
| `tempestweb/server/` | FastAPI + WebSocket/SSE host (Mode B). |
| `tempestweb/native/` | Web API capability adapters (Tracks N + T) — core (http, audio, share, geo, clipboard, storage, camera) plus Tier 1-3 web-platform parity (vibration, wakelock, fullscreen, network, sensors, bluetooth, usb, midi, …) and a streaming event channel (T-EV) consumed with `async for`. |
| `tempestweb/observability/` | Telemetry, logger, error boundary, feature flags, auth — adapter pattern (Track O). |
| `tempestweb/pwa/` | Web App Manifest + icon emitter (Track P). |
| `tempestweb/cli/` | `tempestweb new/dev/build/run/sync`. |
| `client/` | Pure-JS DOM renderer (incl. Canvas draw-command execution for charts), Style→CSS, event capture; `pwa/` `sw/` `offline/` `push/` `native/` subdirs. |
| `tests/fixtures/` | Golden wire-format fixtures derived from the core. |

## Conventions

Python: double quotes, full typing (mypy `--strict`), Google docstrings in English,
async-first. Client: **plain JavaScript only** — no TypeScript, no framework, no
build step. See [`CLAUDE.md`](CLAUDE.md).
