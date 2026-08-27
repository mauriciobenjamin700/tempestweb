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

!!! tip "Not a front-end developer? Start with the ready-made screens"
    If what you need is an **admin panel**, a **dashboard**, a **CRUD** screen
    with search and pagination, a settings **form** or a **login** screen, you do
    not have to learn layout, CSS or a single breakpoint.

    The [ready-made screens (presets)](tutorial/presets.md) take **typed data** —
    which entries the menu has, which numbers the dashboard shows, which columns
    the table has — and decide the appearance for you. The result is already
    responsive: the sidebar becomes a drawer on a phone, the cards reflow, the
    table scrolls.

    ```python
    admin_shell(
        title="Console ACME",
        nav=[NavItem("Overview", "overview"), NavItem("Users", "users")],
        active=app.state.tab,
        on_navigate=go_to,
        body=dashboard_page(
            title="Overview",
            kpis=[Kpi("Revenue", "R$ 82,400", delta="+12%", tone="success")],
        ),
    )
    ```

    A whole panel comes out in ~260 lines of Python, with no hand-written
    `Style` — see the full [Admin Console](examples/admin-console.md).

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
    Head straight to [Installation](tutorial/installation.md) and then follow the
    [Tutorial — the Counter](tutorial/index.md). In four short pages you build
    the canonical app and understand the wire contract end to end.

## What you will find here

<div class="grid cards" markdown>

-   :material-rocket-launch: __Start here__

    ---

    [**Installation**](tutorial/installation.md) — the environment in a minute ·
    [**Tutorial — the Counter**](tutorial/index.md) — four short pages, one
    concept each, and the app running in all three modes ·
    [**Using the CLI**](tutorial/cli.md) — `new`, `build`, `dev`, `deploy` ·
    [**Architecture**](architecture.md) — the four layers and why there is only
    one renderer

-   :material-palette: __Building the interface__

    ---

    [**Ready-made components**](tutorial/components.md) — Material 3 fields,
    forms and buttons (and the Brazilian ones) ·
    [**Ready-made screens (presets)**](tutorial/presets.md) — panel, dashboard,
    listing, form and login from data ·
    [**Theming**](tutorial/theming.md) · [**Icons**](tutorial/icons.md) ·
    [**Routing & navigation**](tutorial/routing.md) ·
    [**Best practices**](tutorial/best-practices.md) — how to organise the app,
    and what never belongs inside a handler

-   :material-server-network: __Going to production__

    ---

    [**Security (Mode B)**](advanced/security.md) — auth, origin, limits ·
    [**Deploy**](advanced/deploy.md) — CDN, nginx, scale, metrics ·
    [**Observability**](advanced/observability.md) — telemetry, logs, feature
    flags ·
    [**PWA & offline**](advanced/pwa.md) — installable, service worker, WebPush ·
    [**Offline + backend**](advanced/offline-sync.md) — queue and sync ·
    [**Mode C — transpile**](advanced/transpile.md) — static bundle, SEO ·
    [**Static SSR**](advanced/ssr.md)

-   :material-database: __Data and models__

    ---

    [**Reading remote data**](tutorial/query.md) — a keyed cache, prefix
    invalidation, and an optimistic change that undoes without a round trip ·
    [**Export CSV and XLSX**](advanced/export.md) — the bytes `file.save`
    delivers, with no dependency ·
    [**Permissions in the view**](advanced/access.md) — `can()` to decide what to
    draw (and why that is **not** authorization) ·
    [**Computer vision**](advanced/vision.md) — classify, detect, segment ·
    [**Tabular inference**](advanced/tabular.md) — sklearn in the browser, with
    the manifest that stops a silently wrong prediction ·
    [**Compressing the store**](advanced/storage-codec.md) — measured before
    turning it on

-   :material-book-open-variant: __Look it up__

    ---

    [**API reference**](reference/presets.md) — every signature, across every
    subpackage ·
    [**Native capabilities**](advanced/capabilities.md) and their
    [**reference**](advanced/native-reference.md) ·
    [**Event channel**](advanced/native-events.md) ·
    [**Client from OpenAPI**](advanced/openapi.md) ·
    [**Wire contract**](advanced/wire-contract.md) —
    [`transports`](reference/transports.md) and [`html`](reference/html.md) ·
    [**Server (Mode B)**](reference/server.md) ·
    [**Example gallery**](examples/index.md) — runnable apps, one per recipe ·
    [**When it goes wrong**](troubleshooting.md) — diagnosis by symptom ·
    [**FAQ**](faq.md) ·
    [**Stability**](stability.md) ·
    [**Roadmap**](design-docs.md)

</div>

!!! info "Language"
    This documentation is **bilingual**. Use the language selector at the top of
    the page to switch between **Português (Brasil)** and **English (US)**.

## Relationship to tempestroid

tempestweb is the **web sibling** of
[tempestroid](https://github.com/mauriciobenjamin700), the mobile framework in the
same family. Both follow the **"one tree, multiple renderers"** philosophy and
share the same renderer-agnostic core — the
[`tempest-core`](https://pypi.org/project/tempest-core/) package (IR, `diff`/patch,
state, style, widgets **and the Material 3 component catalog**, which tempestweb
**re-exports** under `tempestweb.components` — see
[Ready-made components](tutorial/components.md)). tempestroid renders to native screens;
tempestweb renders to the DOM. If you already know one, the mental model transfers directly — but
**you don't need to know tempestroid** to use tempestweb.

## Next step

1. **[Install it](tutorial/installation.md)** — one command.
2. **[Build the counter](tutorial/index.md)** — four pages, and you understand
   the whole cycle.
3. After that, follow wherever your problem is: assemble the screen with
   [presets](tutorial/presets.md), or go straight to
   [security and deploy](advanced/deploy.md) if the app already exists.

## Project conventions

Python: double quotes, full typing (`mypy --strict`), Google docstrings in
English, async-first. Client: **plain JavaScript** — no TypeScript, no
framework, no build step.

!!! note "Project status"
    All three modes are **functional today** — the counter and the 40-plus
    examples in the gallery build, render, and pass the full gate. The living
    design docs are still
    versioned in the repository: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    and [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    This documentation reflects the surface already built and links to the plans
    for full detail.
