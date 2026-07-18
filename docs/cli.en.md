# Using the CLI

!!! abstract "What you'll learn"
    The `tempestweb` CLI is your control panel: it **creates** the project, **runs**
    it locally in all three modes, **builds** the artifact, and **packages** it for
    production. This page walks an app from scratch to deploy, one command at a
    time. 🚀

The CLI ships in the `cli` extra:

```bash
pip install "tempestweb[cli]"        # or: uv add "tempestweb[cli]"
pip install "tempestweb[server,cli]" # if you'll also run Mode B
```

Confirm the install:

```bash
tempestweb --version
# tempestweb 0.53.2
```

!!! tip "`-V` is short for `--version`"
    `tempestweb -V` prints the same thing. And `tempestweb --help` (or `-h`) lists
    every subcommand, with an examples block in the epilogue.

---

## The mental model

Before the commands, three ideas that hold for **all** of them:

1. **A mode is chosen on the CLI — never in the app.** Your `app.py` never names a
   mode. You pick `--mode wasm` (A), `--mode server` (B) or `--mode transpile` (C)
   at run/build time. The same code runs in all three. **Omitting `--mode` uses
   the `[dev].mode` from `tempestweb.toml`** (and, absent that field, `wasm`); an
   explicit `--mode` overrides. This holds for `dev`, `build` and `run`.
2. **`--path` takes the project *directory*, never a `.py` file.** The default is
   the current directory (`.`). The CLI discovers the entrypoint itself.
3. **The default entrypoint is `app.py`.** It's a Python module exposing **two**
   callables — `make_state()` (the initial state) and `view(app)` (the widget
   tree). The name is configurable in `tempestweb.toml`.

!!! info "`tempestweb.toml`"
    Every field has a default, so the file is **optional**. It exists to **change**
    a default:

    ```toml
    [project]
    name = "todolist"
    entrypoint = "app.py"   # change to "main.py", "src/app.py", etc.

    [dev]
    mode = "wasm"           # mode used when you omit --mode (dev/build/run)
    port = 8000
    ```

    Without the module exposing `make_state()` **and** `view(app)`, the build fails
    with `must define a callable make_state/view`.

---

## 1. Create the project — `new`

Don't hand-write the files. `new` scaffolds a runnable project:

```bash
tempestweb new todolist
cd todolist
```

It writes four files — a working counter, the config, a README, and a
`.gitignore`:

```text
todolist/
├── app.py              # the UI: make_state() + view() — the starter counter
├── tempestweb.toml     # project config
├── README.md
└── .gitignore
```

Handy options:

| Flag | What it does |
|---|---|
| `--into <dir>` | Create the project **inside** another directory (default: cwd). |
| `--template <default\|pwa>` | `default` is the two-mode counter; `pwa` is an installable/offline PWA (Mode C). |
| `--force` | Write into an existing non-empty directory. |
| `--no-verify` | Skip the proof render (faster, less guarantee). |

!!! tip "Scaffold into the current folder — `tempestweb new .`"
    Pass `.` as the name to scaffold **into the current directory**, instead of
    creating a subdirectory:

    ```bash
    mkdir myapp && cd myapp
    tempestweb new .
    ```

    The project is **named after the directory's basename** (here, `myapp`).
    `new .` **tolerates** pre-existing non-conflicting files (a `.git/`, a
    `LICENSE`, etc.), but **refuses to overwrite** the scaffold files (`app.py`,
    `tempestweb.toml`, `README.md`, `.gitignore`) if any already exist — pass
    `--force` to overwrite anyway.

!!! tip "PWA template"
    `tempestweb new myapp --template pwa` ships with a manifest, service worker, and
    the offline/WebPush skeleton. `new` prints the next step at the end — for the
    PWA template it suggests `tempestweb dev --mode transpile`.

---

## 2. Run locally — `dev`

**`dev` is the single development command** — it builds **and** serves the app
locally with hot-reload. And, since v0.52, it **serves all three modes**:

=== "Mode A (WASM) — default"

    ```bash
    tempestweb dev
    # no --mode: uses [dev].mode from tempestweb.toml (wasm when unset)
    ```

    Python runs in the browser via Pyodide. Saved a file? The browser reloads
    itself (livereload). Great for iterating on the UI with no server.

=== "Mode B (server)"

    ```bash
    tempestweb dev --mode server
    ```

    Starts the real FastAPI host under uvicorn (Python on the server + thin JS
    client over WebSocket). On every edit the CLI **rebuilds and restarts the
    server** automatically. Needs the `server` extra.

=== "Mode C (transpile)"

    ```bash
    tempestweb dev --mode transpile
    ```

    The app is transcribed to native JavaScript (no Python runtime) and served
    statically with livereload.

They all open at `http://127.0.0.1:8000` by default. Override with `--host` and
`--port`:

```bash
tempestweb dev --mode server --host 0.0.0.0 --port 9000 --path ./myapp
```

!!! tip "`dev` to develop, `run` to serve"
    **`dev` serves every mode** with watch + reload — it's the day-to-day command
    while you write code. **`run`** builds once and serves the app **as-is, with no
    watcher** (production-like) — it's what the Dockerfile generated by
    `tempestweb deploy` runs. Same modes, same flags; only the watcher differs.

!!! info "`dev` never serves a stale cache"
    In the static modes (wasm/transpile) the app is a **PWA with a cache-first
    service worker**. In `dev` that would get in your way — you'd see the old
    bundle. So `tempestweb dev` **does not register the service worker**: it
    injects a kill-switch that unregisters any existing worker and clears all
    caches, so **every reload serves the freshly rebuilt bundle**. `run` /
    `build` / `deploy` keep the caching worker — in production that cache is what
    makes repeat loads fast.

!!! check "Done when"
    The terminal shows `tempestweb dev: serving <app> at http://127.0.0.1:8000
    (mode=wasm); edit a file to reload. Ctrl-C to stop.`, you open the browser and
    see the counter. Editing `app.py` reloads the page (A/C) or restarts the server
    (B).

---

## 3. Build the artifact — `build`

When you're ready to publish, `build` emits the chosen mode's artifact to
`dist/<mode>/`:

```bash
tempestweb build --mode wasm       # static Pyodide bundle   → dist/wasm/
tempestweb build --mode transpile  # native JS, CDN-servable → dist/transpile/
tempestweb build --mode server     # FastAPI app → dist/server/
```

Options:

| Flag | What it does |
|---|---|
| `--path <dir>` | Project directory (default: cwd). |
| `--out <dir>` | Output directory (default: `<project>/dist/<mode>`). |
| `--offline` | (`wasm` only) vendor the Pyodide runtime + wheels so it boots offline. |

!!! note "Offline Mode A"
    `tempestweb build --mode wasm --offline` downloads Pyodide and the wheels at
    build time, so the final bundle doesn't depend on a CDN at runtime — it even
    opens with no network.

---

## 4. Package for production — `deploy`

The static modes (A/C) are just files: publish `dist/` to any CDN. **Mode B**
needs a reverse-proxy and TLS — `deploy` writes those files for you (nginx +
Dockerfile + docker-compose + a `DEPLOY.md`):

```bash
tempestweb deploy --tls --server-name app.example.com
```

Options:

| Flag | What it does |
|---|---|
| `--out <dir>` | Where to write the files (default: `<project>/deploy`). |
| `--server-name <host>` | nginx `server_name` (your domain; default: `_`). |
| `--tls` | Emit a TLS (443) block + HTTP→HTTPS redirect. |
| `--replicas <n>` | Number of app upstream replicas in nginx (default: 1). |
| `--no-sticky` | Drop `ip_hash` (use with a `RedisSessionRouter` to scale SSE out). |
| `--force` | Overwrite existing deploy files. |

Then just follow the generated `DEPLOY.md`. See the full guide in
[Deploy to production](deploy.md).

---

## 5. Utility commands

### `vapid` — keys for WebPush

WebPush (Track P) needs a VAPID keypair. Generate one:

```bash
tempestweb vapid           # prints a human-readable public_key / private_key
tempestweb vapid --env     # prints VAPID_PUBLIC_KEY= / VAPID_PRIVATE_KEY= lines
```

!!! danger "Keep the private key safe"
    Export the private one as `VAPID_PRIVATE_KEY` (a server secret) and share only
    the public one with the client. See [PWA & offline](pwa.md).

### `sync` — pure-Python deps in Mode A

Mode A runs on Pyodide, which doesn't have your full environment. `sync` fills
`[wasm].modules` in `tempestweb.toml` with the project's installed pure-Python
dependencies, so they're bundled into the artifact:

```bash
tempestweb sync            # writes tempestweb.toml
tempestweb sync --dry-run  # just shows what would be added
```

### `gen api` — a typed client from OpenAPI

Generate `@dataclass` models + service classes from an OpenAPI 3.x spec (a
FastAPI backend's `/openapi.json`, or a file):

```bash
tempestweb gen api http://127.0.0.1:8000/openapi.json --out api
tempestweb gen api ./openapi.json --out api   # from a file
```

One package per tag, each with `schemas.py` + `service.py`. Details in
[Generate a client from OpenAPI](openapi.md).

---

## 6. Code quality

You write **typed Python** — so the CLI takes care of that Python's quality too.
Seven commands run `ruff`, `mypy`, and `pytest` **against your project**, with a
layer of opinion on top that you can loosen or tighten. 🚀

!!! warning "Run from the project directory"
    Like everything on the CLI, these commands take the project **directory** via
    `--path` (default: the current directory). Run them from your app's root —
    they scope ruff/mypy/pytest to that path.

!!! info "Needs ruff, mypy, and pytest installed"
    The commands **shell out** to those tools — they don't bundle a copy. The CLI
    prefers the binary on your `PATH`; if it can't find it, it falls back to
    `uv run <tool>`. Install them in your environment (`pip install ruff mypy
    pytest`) or have [uv](https://docs.astral.sh/uv/) on your `PATH`.

### Start with the gate — `check`

`check` is the **full gate**: it runs the four steps in sequence and **stops at
the first error**, all scoped to the project's `--path`.

```bash
tempestweb check
```

The order is always the same:

```text
1. ruff check           # lint
2. ruff format --check  # formatting (read-only)
3. mypy                 # typing
4. pytest               # tests
```

Before each step `check` echoes the command (to stderr) and shows the tool's own
output. On a clean project:

```text
$ ruff check .
All checks passed!
$ ruff format --check .
1 file already formatted
$ mypy .
Success: no issues found in 1 source file
$ pytest .
no tests ran in 0.01s
```

When a step fails, `check` **stops right there** (returning that step's exit
code) — the later steps do not run:

```text
$ ruff check .
All checks passed!
$ ruff format --check .
Would reformat: app.py
1 file would be reformatted
```

!!! note "No tests yet? That's fine"
    `pytest` reports "no tests collected" (exit 5) on a brand-new project; `check`
    treats that as **success**, so the gate passes before you write your first
    test.

!!! tip "It's the same gate as CI"
    Run `tempestweb check` before every commit. It's the one-command version of
    what the CI pipeline does — if it passes locally, it passes there.

### The individual commands

When you want just one step (or want to **fix**, not only report), use the
individual commands:

| Command | Runs | Writes files? |
|---|---|---|
| `tempestweb lint` | `ruff check` | No (report only) |
| `tempestweb fix` | `ruff check --fix` + `ruff format` | **Yes** |
| `tempestweb format` | `ruff format` | **Yes** |
| `tempestweb fmt-check` | `ruff format --check` | No (read-only) |
| `tempestweb type` | `mypy` | No |
| `tempestweb test` | `pytest` | No |

The most common flow: report with `lint`, fix with `fix`.

```bash
tempestweb lint            # what's wrong?
tempestweb fix             # fix what can be fixed automatically
```

`fix` applies ruff's **safe** autofixes and reformats. To also apply the fixes
ruff marks as *unsafe*, pass `--unsafe`:

```bash
tempestweb fix --unsafe    # includes ruff's unsafe autofixes
```

`test` filters tests by `--path`, and treats pytest's **exit code 5** ("no tests
collected") as **success** — a project with no tests yet isn't a broken project:

```bash
tempestweb test                    # run the project's suite
tempestweb test --path ./myapp     # scoped to a subdirectory
```

!!! note "pytest exit 5 = success"
    If pytest finds no tests (exit 5), `tempestweb test` (and `tempestweb check`)
    treat it as ✅. That keeps the gate from breaking on an app that hasn't written
    tests yet.

### The three strictness levels

`lint`, `fix`, `type`, and `check` honor a **strictness** model — a layer of
opinion **on top of** your own ruff/mypy config. It only **adds** rules; it
**never loosens** what you already configured.

| Level | ruff adds (`--extend-select`) | mypy adds |
|---|---|---|
| `lenient` | no extra ANN rules | no extra flag |
| `standard` *(default)* | `ANN001`, `ANN201`, `ANN202`, `ANN205`, `ANN206` | `--ignore-missing-imports` |
| `strict` | `ANN001`, `ANN002`, `ANN003`, `ANN201`, `ANN202`, `ANN204`, `ANN205`, `ANN206` | `--strict` |

In plain terms: `standard` requires types on parameters and on public function
returns; `strict` also demands `*args`/`**kwargs` and dunder methods, and turns on
`mypy --strict`; `lenient` adds nothing — it stays with your own config.

!!! danger "`Any` is always valid — `ANN401` is never enabled"
    No level enables the **`ANN401`** rule (ban `typing.Any`). `Any` is a
    **legitimate** annotation — using it on purpose *is* typing, not skipping it.
    You choose `Any` when you need it; the CLI will never punish you for it.

### Configure the level — `tempestweb.toml [quality]`

The default is `standard`. To change the level for the whole project, write it in
`tempestweb.toml`:

```toml
[quality]
typing_strictness = "standard"   # "lenient" | "standard" | "strict"
```

`tempestweb new` already writes this block in the scaffolded `tempestweb.toml`,
with `"standard"`.

For **a single invocation**, override with `--strictness` without touching the
file:

```bash
tempestweb check --strictness strict     # tighten just this run
tempestweb lint  --strictness lenient    # loosen just this run
```

!!! check "Done when"
    `tempestweb check` exits `0` with every step reporting clean. That's the same
    green CI expects — commit with confidence.

---

## Subcommand reference

Every command that builds/serves takes the project **directory** via `--path`
(default: current directory) — **never** a positional `.py` file.

| Command | What it does | Key flags |
|---|---|---|
| `tempestweb new <name>` | Scaffold a runnable project. | `--into`, `--template <default\|pwa>`, `--force`, `--no-verify` |
| `tempestweb dev` | **Develop locally with watch + reload — serves all modes.** | `--mode <wasm\|server\|transpile>`, `--path`, `--host`, `--port` |
| `tempestweb build` | Emit the artifact to `dist/<mode>/`. | `--mode`, `--path`, `--out`, `--offline` |
| `tempestweb run` | **Serve the app as built, no watcher (production-like).** | `--mode`, `--path`, `--host`, `--port`, `--offline` |
| `tempestweb deploy` | Write the deploy files (nginx + Docker + guide). | `--out`, `--server-name`, `--tls`, `--replicas`, `--no-sticky`, `--force` |
| `tempestweb vapid` | Generate a VAPID keypair for WebPush. | `--env` |
| `tempestweb sync` | Fill `[wasm].modules` with pure-Python deps. | `--path`, `--dry-run` |
| `tempestweb gen api <src>` | Generate a typed client (dataclasses + services) from OpenAPI. | `--out` |
| `tempestweb lint` | `ruff check` on the project. | `--path`, `--strictness <lenient\|standard\|strict>` |
| `tempestweb fix` | `ruff check --fix` + `ruff format` (writes). | `--path`, `--strictness`, `--unsafe` |
| `tempestweb format` | `ruff format` (writes). | `--path` |
| `tempestweb fmt-check` | `ruff format --check` (read-only). | `--path` |
| `tempestweb type` | `mypy` on the project. | `--path`, `--strictness` |
| `tempestweb test` | `pytest` (exit 5 = success). | `--path` |
| `tempestweb check` | Gate: `ruff check` → `ruff format --check` → `mypy` → `pytest`. | `--path`, `--strictness` |
| `tempestweb --version` / `-V` | Print the installed version. | — |

## Recap

- **`new`** creates; **`dev`** develops (all **three** modes, with watch + reload);
  **`run`** serves as built (no watcher, production-like); **`build`** emits the
  artifact; **`deploy`** packages Mode B for production.
- The mode is chosen on the CLI (`--mode`), never in `app.py`.
- `--path` takes the **directory**; the default entrypoint is `app.py`
  (configurable), and must expose `make_state()` + `view(app)`.
- **`check`** is the quality gate (`ruff check` → `ruff format --check` → `mypy` →
  `pytest`, stopping at the first error); `lint`/`fix`/`format`/`fmt-check`/`type`/
  `test` are the individual steps. The `[quality] typing_strictness` level
  (lenient/standard/strict, default `standard`) adds rules on top of your config,
  never loosens it — and **`ANN401` is never enabled** (`Any` is valid).

Ready? Head to the [Tutorial](tutorial/index.md) and build the counter. 🚀
