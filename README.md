# tempestweb

📚 **Documentation:** [Português (Brasil)](https://mauriciobenjamin700.github.io/tempestweb/)
· [English (US)](https://mauriciobenjamin700.github.io/tempestweb/en/) — bilingual
docs site (PT-BR default + EN-US), deployed to GitHub Pages. A linear
[Tutorial](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/), an
[Advanced Guide](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/capabilities/),
and a generated
[API reference](https://mauriciobenjamin700.github.io/tempestweb/en/reference/presets/)
covering every subpackage.

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
([PT-BR](https://mauriciobenjamin700.github.io/tempestweb/examples/)) —
single-concept demos (stopwatch, forms, data table/grid, kanban, chat, theming,
i18n, canvas charts, app shells, native capabilities, observability, PWA/WebPush,
a Mode C tour, and a server-mode walkthrough), each running unchanged across the
execution modes.

Not a front-end developer? The
**[ready-made screens](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/presets/)**
([PT-BR](https://mauriciobenjamin700.github.io/tempestweb/tutorial/presets/))
build an admin panel, dashboard, CRUD listing, settings form or login screen
from typed data — no `Style`, no font size, no breakpoint. A whole panel in ~260
lines: see the
**[Admin Console](https://mauriciobenjamin700.github.io/tempestweb/en/examples/admin-console/)**.

Building an admin panel? Skip the chrome with **[ready-made screens](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/presets/)**
([PT-BR](https://mauriciobenjamin700.github.io/tempestweb/tutorial/presets/)) — an admin
shell, a KPI dashboard, a searchable list, forms and an auth screen, described
with typed records instead of assembled widget by widget. They come with the
responsive behaviour inline styles cannot express: a sidebar that collapses to a
drawer, grids that reflow, a table that scrolls under a sticky header, and a
print layout without the chrome. No CSS, no breakpoints of your own.

Building something real? Read the **[App architecture & best practices](https://mauriciobenjamin700.github.io/tempestweb/tutorial/best-practices/)**
guide ([EN](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/best-practices/)) —
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
(`app.py` by default, configurable). `tempestweb dev` runs any mode locally with
hot-reload — pick the mode at dev/build time, never in the app:

```bash
tempestweb dev   --mode wasm       --path myapp   # Mode A: Python in the browser
tempestweb dev   --mode server     --path myapp   # Mode B: FastAPI + WebSocket
tempestweb dev   --mode transpile  --path myapp   # Mode C: native JS bundle
tempestweb build --mode transpile  --path myapp   # emit a static, CDN-servable bundle
```

> `dev` serves **all three modes** with watch + reload — including **Mode B
> (server)**, which rebuilds and restarts on every edit. To serve the built app
> **without** a watcher (production-like), use `tempestweb run --mode server` — it's
> what the generated deploy Dockerfile runs. Every command takes the project
> **directory** via `--path` (default: cwd) — not a positional `.py` file. Check
> your install with `tempestweb --version`.

Talking to a FastAPI backend? Generate a typed client from its OpenAPI spec —
`@dataclass` models + service classes, one package per route group, working in
all three modes (the Python analog of `tempest-react-sdk`'s `tempest gen api`):

```bash
tempestweb gen api http://127.0.0.1:8000/openapi.json --out api
```

Full walkthrough: the [Using the CLI](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/cli/),
[Generate a client from OpenAPI](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/openapi/),
[Installation](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/installation/)
and [Tutorial](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/) guides.

## Code quality

You write typed Python, so the CLI polices that Python too. `tempestweb check` is
the one-command gate — it runs `ruff check` → `ruff format --check` → `mypy` →
`pytest` against your project and stops at the first error:

```bash
tempestweb check                       # the full gate
tempestweb lint / fix / format / fmt-check / type / test   # individual steps
```

The gate layers opinion on top of your own ruff/mypy config via a strictness
level — `[quality] typing_strictness` in `tempestweb.toml` (`lenient` |
`standard` | `strict`, default `standard`, `tempestweb new` scaffolds it). It only
**adds** rules, never loosens yours, and `ANN401` is never enabled — `Any` is a
valid annotation. `--strictness` overrides per invocation. Full details in the
[Code quality](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/cli/#code-quality)
guide.

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
[capability reference](https://mauriciobenjamin700.github.io/tempestweb/advanced/native-reference/)
([EN](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/native-reference/)) and
the [event-channel guide](https://mauriciobenjamin700.github.io/tempestweb/advanced/native-events/).

## Static SSR — `render_to_html`

Another render target, alongside the interactive modes: the **same** typed tree
renders to a **static HTML string** on the server — no JavaScript, no DOM, no
runtime. HTML is just another leaf renderer.

```python
from tempest_core import Column, Text, Button, Style
from tempest_core import Edge
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
See the [Static SSR guide](https://mauriciobenjamin700.github.io/tempestweb/advanced/ssr/)
([EN](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/ssr/)).

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
`tempest_core`**: every widget it builds, MD3 styling, state-with-methods,
navigation (routes + URL), i18n, theme + responsiveness, native capabilities
(http/storage/cookies/…), field validators and both declarative and imperative
animation. The `tempestweb build/dev --mode transpile` CLI emits a static,
CDN-servable bundle that is a **first-class PWA — installable and offline out of
the box** (manifest + cache-first service worker precaching the whole shell;
customize via `[pwa]` in `tempestweb.toml`, or turn either half off with
`[pwa] enabled = false` when the app is behind a login and gains nothing from
precache).

See the canonical [`examples/transpile-tour`](examples/transpile-tour/app.py) —
one app exercising the whole surface — and the guide
([PT](https://mauriciobenjamin700.github.io/tempestweb/advanced/transpile/) ·
[EN](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/transpile/)). It is a
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

## Computer vision (ONNX)

```bash
pip install "tempestweb[vision]"   # pulls ort-vision-sdk + numpy
```

```python
from tempestweb.vision import Detector, to_detection_schemas

det = await Detector.create("./models/yolov8n.onnx", labels="coco")
result = (await det.predict("./images/street.jpg"))[0]
for d in result:
    print(d.name, d.conf, d.box.xyxy)          # Ultralytics-style views
payload = to_detection_schemas(result)          # JSON for a tempest-fastapi-sdk backend
```

`Classifier` / `Detector` / `Segmenter` share the **same input/output contract as
[`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/) and
`tempest-fastapi-sdk`'s vision layer**, but run the model over the `native.onnx`
bridge (onnxruntime-web) so inference works in the browser — no `onnxruntime`
wheel needed. Preprocessing, postprocessing and the `.boxes`/`.probs`/`.masks`
result objects are ort-vision-sdk's, unchanged; only the model run crosses the
(async) bridge, so construction and `predict` are awaited. See the
[Computer vision guide](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/vision/).

## Data on the screen (`query` · `export` · `access`)

Three pure-Python layers between the widgets and the network — no browser needed,
no dependency added.

```python
from tempestweb.query import QueryCache, keys, offset_page, upsert_by_id

USERS, CACHE = keys("users"), QueryCache()

response = await CACHE.fetch(USERS.list(page=1), lambda: native.http.request("GET", "/api/users?page=1"))
page = offset_page(response.json)

with CACHE.optimistic(USERS.all(), lambda rows: upsert_by_id(rows, edited)):
    await native.http.request("PATCH", "/api/users/7", json=edited)   # rolls back if this raises
```

`query` keeps the **read** side: keys are tuples, so invalidation is by prefix
(`CACHE.invalidate(USERS.all())` reaches every cached page), concurrent reads of
one key collapse into one request, and the optimistic block restores exactly what
it replaced — no round trip to undo something the server never accepted.

`export` turns rows into CSV/XLSX **bytes** for `native.file.save`, closing the
four holes a hand-rolled encoder always leaves — separator inside a field, quote
inside the text, the missing BOM, and an XLSX date written as a bare number.
`access` holds the role → permission map so the `view` can ask
`access.can("users:delete")` instead of spreading `if state.role == "admin"`.

> :warning: `access` is **not** authorization. Hiding a button stops nobody from
> calling the endpoint behind it — the server decides, with the signing key.

See the [Reading remote data](https://mauriciobenjamin700.github.io/tempestweb/en/tutorial/query/),
[Export](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/export/) and
[Permissions](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/access/) guides.

## Tabular inference (ONNX, or no runtime at all)

```python
from tempestweb.tabular import TabularPredictor

PREDICTOR = TabularPredictor("/models/risk.onnx", manifest="/models/risk.json")
prediction = await PREDICTOR.predict({"age": 30, "income": 3200.0, "tenure_months": 18})
print(prediction.score, prediction.label, prediction.probabilities)
```

The sibling of `vision`, for the commonest kind of ML in a business app: a risk
score, a demand forecast, a lead classification — running **in the browser**, so
it still works offline.

The **manifest** is the point. An ONNX model is a function from an unlabelled
vector of floats to a number, so the order carries all the meaning and nothing in
the runtime checks it: a row written `{"idade": 30}` for a model trained on `age`
reads a zero and answers a plausible, wrong score. With a manifest that becomes
`MissingFeatureError`, naming the feature that is missing **and** the one that was
sent instead. Training and export are a build step in a throwaway venv
(`uvx --with skl2onnx …`), never a runtime dependency.

**For a linear model or a tree ensemble, drop the runtime instead of the model.**
`onnxruntime-web` is 13.96 MB of WebAssembly (3.58 MB gzipped) against a 660-byte
`LogisticRegression` — for an app whose only model is tabular, the runtime *is*
the download. `CompactPredictor` reads the `.tmc` format in stdlib Python
(`struct`, `array`, `math`), because a linear model is a dot product and a tree is
a chain of comparisons:

```python
from tempestweb.tabular import CompactPredictor

PREDICTOR = CompactPredictor("/models/risk.tmc")          # the file is the manifest
prediction = await PREDICTOR.predict({"age": 30, "income": 3200.0})
```

The `.tmc` is written by `tempest_fastapi_sdk.modelops.export_sklearn_to_compact`,
which verifies the bytes against scikit-learn's own predictions and refuses to
write a file that disagrees, and it records `feature_names` and `classes` in its
own header — so there is no second file to keep in sync. The bytes reach Python
through the `compact.load` capability, over the same asset cache `onnx.load` uses.
Measured in real Chrome with no `onnxruntime-web` anywhere: 6.3 ms from cold to
the first prediction, a 0.2 ms p95 per row. Gradient boosting is a different
reader and the exporter refuses it — that one stays on `TabularPredictor`. See the
[Tabular guide](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/tabular/).

## Deploy (server mode)

```bash
tempestweb deploy --server-name app.example.com --tls    # -> deploy/
cd deploy && docker compose up --build
```

Generates a tailored `nginx.conf` (WebSocket upgrade, streaming timeouts, sticky
`ip_hash`, optional TLS), a `Dockerfile`, `docker-compose.yml` and a `DEPLOY.md`.
Harden the app with a `SecurityConfig` (auth, CORS, limits, rate limiting,
headers) — see the [Security](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/security/)
and [Deploy](https://mauriciobenjamin700.github.io/tempestweb/en/advanced/deploy/) guides.
Static modes (A/C) need no server — publish the build to any CDN.

## Develop

```bash
uv venv && uv pip install -e ".[dev,server,cli]"
make check          # ruff + mypy + pytest + JS (jsdom) tests
```

## Layout

| Path | What |
|---|---|
| Path | What |
|---|---|
| `tempest-core` (dependency) | Renderer-agnostic engine — IR/reconciler/state/style/widgets (`import tempest_core`), extracted from tempestroid. |
| `tempestweb/components/` | Native fields + forms (EmailField, PasswordField, LoginForm, …) plus the re-exported tempest-core library of Material 3 components (Card, DataTable, Tabs, Drawer, Alert, BarChart/LineChart, …). |
| `tempestweb/presets/` | Ready-made screens built from data — panel, dashboard, listing, form, login. |
| `tempestweb/transports/` | The one seam between modes (`base.py` Protocol, `wasm.py`, `websocket.py`, `sse.py`). |
| `tempestweb/html/` | Static SSR leaf renderer — `render_to_html` / `render_document` / `style_to_css` (Python port of `client/style.js`). |
| `tempestweb/transpile/` | **Mode C:** `ast`-based Python→JS compiler for the app layer. Paired with the native runtime in `client/transpile/` (`diff.js` · `widgets.js` · `runtime.js`). |
| `tempestweb/server/` | FastAPI + WebSocket/SSE host (Mode B). |
| `tempestweb/native/` | Web API capability adapters (Tracks N + T) — core (http, audio, share, geo, clipboard, storage, camera) plus web-platform parity (vibration, wakelock, fullscreen, network, sensors, bluetooth, usb, midi, …), image processing (`imaging`), device profile (`device`), and a streaming event channel (T-EV) consumed with `async for`. |
| `tempestweb/query/` | The read side of remote data — keyed cache, prefix invalidation, single-flight, pagination, optimistic updates with an exact rollback. |
| `tempestweb/access/` | Role → permission map and unverified token claims, so the `view` can decide what to draw. **Not** authorization. |
| `tempestweb/export/` | CSV and XLSX bytes generated in Python, for `native.file.save` to deliver. No dependency. |
| `tempestweb/vision/` | Classification, detection and segmentation over ONNX in the browser. Needs the `[vision]` extra. |
| `tempestweb/tabular/` | Inference over a row of numbers, with a feature manifest that stops a silently wrong prediction: `TabularPredictor` over sklearn→ONNX, and `CompactPredictor` reading `.tmc` in stdlib Python with **no inference runtime**. |
| `tempestweb/observability/` | Telemetry, logger, error boundary, feature flags, auth — adapter pattern (Track O). |
| `tempestweb/pwa/` | Web App Manifest + icon emitter (Track P). |
| `tempestweb/cli/` | `tempestweb new/dev/build/run/sync/gen`. |
| `client/` | Pure-JS DOM renderer (incl. Canvas draw-command execution for charts), Style→CSS, event capture; `pwa/` `sw/` `offline/` `push/` `native/` subdirs. |
| `tests/fixtures/` | Golden wire-format fixtures derived from the core. |

## Conventions

Python: double quotes, full typing (mypy `--strict`), Google docstrings in English,
async-first. Client: **plain JavaScript only** — no TypeScript, no framework, no
build step. See [`CLAUDE.md`](CLAUDE.md).
