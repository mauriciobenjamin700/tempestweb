# tempestweb

📚 **Documentation:** [Português (Brasil)](https://mauriciobenjamin700.github.io/tempestweb/)
· [English (US)](https://mauriciobenjamin700.github.io/tempestweb/en/) — bilingual
docs site (PT-BR default + EN-US), deployed to GitHub Pages.

> Build web apps in **typed Python**. One declarative widget tree, a **DOM**
> renderer, and **three execution modes** that share 100% of the application code:
> **Mode A (WASM)** runs your Python in the browser via Pyodide; **Mode B
> (server)** runs it on the server (FastAPI) and talks to a thin JS client over
> **WebSocket or SSE**; **Mode C (transpile, experimental)** transcribes your
> Python to **native JavaScript** — zero Python runtime, static hosting, great
> first-paint/SEO. Installable **PWA**, **offline-first** (service worker +
> IndexedDB), and **WebPush** are first-class — parity with `tempest-react-sdk`.

Sister project to [tempestroid](../tempestroid) — same "one tree, multiple
renderers" architecture. The renderer-agnostic engine (IR, reconciler, state,
style, widgets) is shared; tempestweb adds a **DOM** leaf renderer (pure
JavaScript, no framework, no build step, no TypeScript) and two patch transports.

## Status

🚧 Early construction. See the design docs:

- [`docs/plan.md`](docs/plan.md) — full design and phase plan.
- [`docs/roadmap.md`](docs/roadmap.md) — phase checklist.
- [`docs/arquitetura.md`](docs/arquitetura.md) — architecture.
- [`docs/contract.md`](docs/contract.md) — the Python↔client wire format.
- [`docs/agents/MANIFEST.md`](docs/agents/MANIFEST.md) — parallel agent task plan.

Want runnable apps? Browse the **[Example Gallery](https://mauriciobenjamin700.github.io/tempestweb/en/examples/)**
([PT-BR](https://mauriciobenjamin700.github.io/tempestweb/examples/)) — 41 single-concept
demos (stopwatch, forms, data table/grid, kanban, chat, theming, i18n, canvas
charts, app shells, native capabilities, observability, PWA/WebPush, and a
server-mode walkthrough), each running unchanged in both modes.

Building something real? Read the **[App architecture & best practices](https://mauriciobenjamin700.github.io/tempestweb/best-practices/)**
guide ([EN](https://mauriciobenjamin700.github.io/tempestweb/en/best-practices/)) —
the ideal layered structure (routes · pages · components · styles · controllers ·
services · storages · schemas · utils · core), mirroring `tempest-fastapi-sdk`, so
your app doesn't rot into garbage code.

## How it works

```text
   view(app) ──build──▶ Node tree (IR)        ← shared core (vendored from tempestroid)
                            │
                          diff
                            ▼
                        [ Patch ]              insert / remove / update / reorder / replace
                       ╱          ╲
              Mode A transport   Mode B transport
              (pyodide.ffi)       (WebSocket | SSE)
                       ╲          ╱
                  client/ (pure JS): apply patches to the DOM
                  + Style→CSS + event capture                  ← same code in both modes
```

The application's `view()` never names a transport — the same `examples/counter/app.py`
runs under `--mode wasm` and `--mode server` unchanged. Capabilities (`native/`:
http, audio, share, geolocation, clipboard, storage, camera) are typed awaitables
with the same Python API in both modes — Mode A calls the Web API in-process, Mode
B proxies it over a round-trip (see [`docs/contract.md`](docs/contract.md)).

## Static SSR — `render_to_html`

A third render target, alongside the two interactive modes: the **same** typed
tree renders to a **static HTML string** on the server — no JavaScript, no DOM, no
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

## Mode C — transpile to native JS (experimental) 🧪

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
with a JS `diff` locked against a core-derived golden. **Experimental (spike
C0)**: MD3 style fidelity, a `build --mode transpile` CLI, and a wider subset are
next (phases C1–C5). See [`docs/modo-c-transpile.md`](docs/modo-c-transpile.md).

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
| `tempestweb/transpile/` | **Mode C (experimental):** `ast`-based Python→JS compiler for the app layer. Paired with the native runtime in `client/transpile/` (`diff.js` · `widgets.js` · `runtime.js`). |
| `tempestweb/server/` | FastAPI + WebSocket/SSE host (Mode B). |
| `tempestweb/native/` | Web API capability adapters — http, audio, share, geo, clipboard, storage, camera (Track N). |
| `tempestweb/observability/` | Telemetry, logger, error boundary, feature flags, auth — adapter pattern (Track O). |
| `tempestweb/pwa/` | Web App Manifest + icon emitter (Track P). |
| `tempestweb/cli/` | `tempestweb new/dev/build/run/sync`. |
| `client/` | Pure-JS DOM renderer (incl. Canvas draw-command execution for charts), Style→CSS, event capture; `pwa/` `sw/` `offline/` `push/` `native/` subdirs. |
| `tests/fixtures/` | Golden wire-format fixtures derived from the core. |

## Conventions

Python: double quotes, full typing (mypy `--strict`), Google docstrings in English,
async-first. Client: **plain JavaScript only** — no TypeScript, no framework, no
build step. See [`CLAUDE.md`](CLAUDE.md).
