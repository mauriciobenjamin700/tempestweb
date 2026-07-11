# tempestweb 🌩️

<p align="center"><em>Build web apps in <strong>typed Python</strong>. One declarative
widget tree, a <strong>DOM</strong> renderer, and <strong>three execution modes</strong>
that share 100% of the application code.</em></p>

---

**tempestweb** is a framework for building web apps by writing **typed Python**.
You describe the UI as a **declarative tree of widgets** in a `view()` function,
and the framework renders it to the **DOM**. The same `view()`, without changing a
line, runs in **three execution modes**:

<div class="grid cards" markdown>

-   :material-language-python: __Mode A — WASM__

    ---

    Your Python runs **in the browser** via Pyodide. Like PyScript. Fully
    offline after the initial load.

    **When to use:** full offline, zero server infra, fast prototyping.

-   :material-server: __Mode B — Server__

    ---

    Your Python runs **on the server** (FastAPI) and talks to a thin JS client
    over WebSocket or SSE. Like Phoenix LiveView.

    **When to use:** server-side logic, central state, live data.

-   :material-language-javascript: __Mode C — transpile__

    ---

    The app layer is **transcribed to native JavaScript** at build time. Zero
    Python in the browser — a static bundle any CDN can serve.

    **When to use:** installable PWA, great SEO and first-paint, zero server cost.

</div>

The trick: the app **never names a transport**. The very same
`examples/counter/app.py` runs under `--mode wasm`, `--mode server` and
`--mode transpile` without changing a line. 🚀

!!! question "Which mode should I pick?"
    - Need **SEO, fast first-paint, and a static server-free bundle**? →
      **Mode C (transpile)** — the default choice for public sites/PWAs.
    - Need to keep **logic or state on the server** (live data, secrets)? →
      **Mode B (server)**.
    - Want **live Python in the browser** to prototype or run Python libs
      client-side? → **Mode A (WASM)**.

    You never decide this in code — only at `build --mode` time. Start with the
    [Tutorial](tutorial/index.md), which runs the counter in all three modes.

## How it works

```text
   view(app) ──build──▶ Node tree (IR)        ← shared core
                            │
                          diff
                            ▼
                        [ Patch ]              insert / remove / update / reorder / replace
                    ╱        │        ╲
          Mode A          Mode B          Mode C
       (pyodide.ffi)   (WebSocket/SSE)  (app → native JS, diff in JS)
                    ╲        │        ╱
                  client/ (pure JS): apply patches to the DOM
                  + Style→CSS + event capture     ← same code in all three modes
```

The `view()` function produces a **widget tree** (IR). The reconciler `diff`s
the old tree against the new one and emits **patches** — plain serialized data.
In Modes A and B the `diff` runs in Python and patches travel over a transport;
in **Mode C** the app layer is transcribed to JS, so the `diff` runs natively in
the browser. In all of them the JS client only knows how to consume a patch and
mutate the DOM — it does not care where the patch came from. That is why the
renderer is the **same** across all three modes.

!!! tip "Where to start"
    Head straight to [Installation](installation.md) and then follow the
    [Tutorial — the Counter](tutorial/index.md). In four short pages you build
    the canonical app and understand the wire contract end to end.

## What you will find here

- **[Installation](installation.md)** — set up your environment in a minute.
- **[Architecture](architecture.md)** — the four layers and why the renderer is
  shared.
- **[Tutorial](tutorial/index.md)** — build the counter, one concept per page, and
  run it in all three modes.
- **[Mode C — transpile](transpile.md)** — Python → native JavaScript: static
  bundle, SEO, turnkey PWA.
- **[PWA & offline](pwa.md)** — installable app, service worker, IndexedDB, WebPush.
- **[Capabilities](capabilities.md)** — typed Web APIs (geolocation, clipboard,
  camera) as Python awaitables.
- **[Wire contract](wire-contract.md)** — the Python↔client wire format.
- **[Observability](observability.md)** — telemetry, logger, feature flags, auth.
- **[Roadmap & design docs](design-docs.md)** — what's coming and the project's
  living design plans.

!!! info "Language"
    This documentation is **bilingual**. Use the language selector at the top of
    the page to switch between **Português (Brasil)** and **English (US)**.

## Relationship to tempestroid

tempestweb is the **web sibling** of
[tempestroid](https://github.com/mauriciobenjamin700), the mobile framework in the
same family. Both follow the **"one tree, multiple renderers"** philosophy and
share the same renderer-agnostic core — the
[`tempest-core`](https://pypi.org/project/tempest-core/) package (IR, `diff`/patch,
state, style, widgets). tempestroid renders to native screens; tempestweb renders
to the DOM. If you already know one, the mental model transfers directly — but
**you don't need to know tempestroid** to use tempestweb.

## Project conventions

Python: double quotes, full typing (`mypy --strict`), Google docstrings in
English, async-first. Client: **plain JavaScript** — no TypeScript, no
framework, no build step.

!!! note "Project status"
    All three modes are **functional today** — the counter and the 50 examples
    build, render, and pass the full gate. The living design docs are still
    versioned in the repository: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    and [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    This documentation reflects the surface already built and links to the plans
    for full detail.
