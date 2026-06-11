# tempestweb 🌩️

<p align="center"><em>Build web apps in <strong>typed Python</strong>. One declarative
widget tree, a <strong>DOM</strong> renderer, and <strong>two execution modes</strong>
that share 100% of the application code.</em></p>

---

**tempestweb** is the web sibling of
[tempestroid](https://github.com/mauriciobenjamin700) — the same **one tree,
multiple renderers** idea. You write a `view()` function in Python and it runs,
unchanged, in two modes:

<div class="grid cards" markdown>

-   :material-language-python: __Mode A — WASM__

    ---

    Your Python runs **in the browser** via Pyodide. Like PyScript. Fully
    offline after the initial load.

-   :material-server: __Mode B — Server__

    ---

    Your Python runs **on the server** (FastAPI) and talks to a thin JS client
    over WebSocket or SSE. Like Phoenix LiveView.

</div>

The trick: the app **never names a transport**. The very same
`examples/counter/app.py` runs under `--mode wasm` and `--mode server` without
changing a line. 🚀

## How it works

```text
   view(app) ──build──▶ Node tree (IR)        ← shared core
                            │
                          diff
                            ▼
                        [ Patch ]              insert / remove / update / reorder / replace
                       ╱          ╲
              Mode A transport    Mode B transport
              (pyodide.ffi)       (WebSocket / SSE)
                       ╲          ╱
                  client/ (pure JS): apply patches to the DOM
                  + Style→CSS + event capture     ← same code in both modes
```

The `view()` function produces a **widget tree** (IR). The reconciler `diff`s
the old tree against the new one and emits **patches** — plain serialized data.
The JS client only knows how to consume a patch and mutate the DOM; it does not
care where the patch came from. That is why the renderer is the **same** in both
modes.

!!! tip "Where to start"
    Head straight to [Installation](installation.md) and then follow the
    [Tutorial — the Counter](tutorial/index.md). In four short pages you build
    the canonical app and understand the wire contract end to end.

## What you will find here

- **[Installation](installation.md)** — set up your environment in a minute.
- **[Architecture](architecture.md)** — the four layers and why the renderer is
  shared.
- **[Tutorial](tutorial/index.md)** — build the counter, one concept per page.
- **[Wire contract](wire-contract.md)** — the Python↔client wire format.
- **[Capabilities](capabilities.md)** — typed Web APIs (geolocation, clipboard,
  camera) as Python awaitables.
- **[PWA & offline](pwa.md)** — installable app, service worker, IndexedDB, WebPush.
- **[Observability](observability.md)** — telemetry, logger, feature flags, auth.
- **[Roadmap & design docs](design-docs.md)** — what's coming and the project's
  living design plans.

!!! info "Language"
    This documentation is **bilingual**. Use the language selector at the top of
    the page to switch between **Português (Brasil)** and **English (US)**.

## Project conventions

Python: double quotes, full typing (`mypy --strict`), Google docstrings in
English, async-first. Client: **plain JavaScript** — no TypeScript, no
framework, no build step.

!!! note "Project status"
    🚧 tempestweb is in **early construction**. The living design docs are
    versioned in the repository: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    and [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    This documentation reflects the surface already built and links to the plans
    for full detail.
