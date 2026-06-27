# tempestweb

📚 **Documentation:** [Português (Brasil)](https://mauriciobenjamin700.github.io/tempestweb/)
· [English (US)](https://mauriciobenjamin700.github.io/tempestweb/en/) — bilingual
docs site (PT-BR default + EN-US), deployed to GitHub Pages.

> Build web apps in **typed Python**. One declarative widget tree, a **DOM**
> renderer, and **two execution modes** that share 100% of the application code:
> **Mode A (WASM)** runs your Python in the browser via Pyodide; **Mode B
> (server)** runs it on the server (FastAPI) and talks to a thin JS client over
> **WebSocket or SSE**. Installable **PWA**, **offline-first** (service worker +
> IndexedDB), and **WebPush** are first-class — parity with `tempest-react-sdk`.

Sister project to [tempestroid](../tempestroid) — same "one tree, multiple
renderers" architecture. The renderer-agnostic engine (IR, reconciler, state,
style, widgets) is shared; tempestweb adds a **DOM** leaf renderer (pure
JavaScript, no framework, no build step, no TypeScript) and two patch transports.

## Status

✅ **Stable & published.** `tempestweb` is on PyPI (latest **0.8.1**). Every track
(W/A/B/P/N/O/E + the `tempest-core` adoption) is merged to `main` with a green gate
(`ruff` ✓ · `mypy --strict` ✓ · `pytest` 484 passed/1 skipped · jsdom 229 pass), and
**both execution modes run an app end-to-end live in the browser** (Mode A via
Pyodide/WASM, in-process and zero-network; Mode B via FastAPI + WebSocket
round-trip), re-verified with Playwright on 0.8.1.

The design docs:

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
   view(app) ──build──▶ Node tree (IR)        ← shared core (the `tempest-core` dependency)
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

## Install

```bash
pip install tempestweb        # or:  uv add tempestweb
```

The base install pulls in `tempest-core` (the renderer-agnostic engine). Add the
extras for the pieces you actually use:

```bash
uv add "tempestweb[server,cli]"     # Mode B host (FastAPI/WebSocket) + the CLI
uv add "tempestweb[webpush]"        # server-side WebPush (P3)
```

| Extra | Pulls in | When you need it |
|---|---|---|
| `server` | `fastapi`, `uvicorn[standard]`, `websockets` | Mode B — Python on the server, thin JS client over WebSocket/SSE. |
| `cli` | `watchfiles`, `tomlkit` | The `tempestweb new/dev/build/run/sync` workflow. |
| `webpush` | `pywebpush` | Server-side WebPush sends (P3). |
| `docs` | `mkdocs-material`, `mkdocs-static-i18n` | Build the bilingual docs site locally. |

Mode A (WASM) needs no extras — the browser + Pyodide are the runtime.

## Develop

```bash
uv venv && uv pip install -e ".[dev,server,cli]"
make check          # ruff + mypy + pytest + JS (jsdom) tests
```

## Layout

| Path | What |
|---|---|
| `tempest-core` (dependency) | Renderer-agnostic engine — IR/reconciler/state/style/widgets (`import tempest_core`), extracted from tempestroid. |
| `tempestweb/components/` | Native fields + forms (EmailField, PasswordField, LoginForm, …) plus the re-exported tempest-core library — **67 Material 3 components** + 10 helpers (Card, DataTable, Tabs, Drawer, Alert, BarChart/LineChart, …) from `import tempestweb.components`. |
| `tempestweb/transports/` | The one seam between modes (`base.py` Protocol, `wasm.py`, `websocket.py`, `sse.py`). |
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
