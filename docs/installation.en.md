# Installation

tempestweb is published on [PyPI](https://pypi.org/project/tempestweb/) — to
**use** the framework, a single `pip install` is all it takes. No frontend build
step: the client is plain JavaScript, bundled by the CLI itself. ✅

!!! tip "User or contributor?"
    - **Just want to use tempestweb in your app?** Stay in the
      [Install from PyPI](#install-from-pypi) section — that's all you need.
    - **Want to contribute to the framework** (run the gate, the tests, these
      docs)? Head to [Installing to contribute](#installing-to-contribute).

## Prerequisites

- **Python 3.11+** (the repository runs on 3.13).

That's all you need to use it. The contributor path also asks for
[uv](https://docs.astral.sh/uv/) and Node.js 18+ — see
[Installing to contribute](#installing-to-contribute).

## Install from PyPI

```bash
pip install tempestweb
```

This installs the core. The **extra capabilities** are optional — install only
what your app uses:

```bash
pip install "tempestweb[server]"          # Mode B (server): FastAPI + websockets
pip install "tempestweb[cli]"             # the dev loop and static bundler
pip install "tempestweb[server,cli]"      # the most common combo
pip install "tempestweb[webpush]"         # push notifications (Track P)
```

| Extra | For |
|---|---|
| `server` | FastAPI, uvicorn, websockets — **Mode B** (Python on the server). |
| `cli` | watchfiles + tomlkit — the dev loop (`tempestweb dev`) and `tempestweb sync`. |
| `webpush` | pywebpush + cryptography — Web Push (Track P). |

!!! note "Modes A (WASM) and C (transpile) have no Python extra"
    **Mode A** runs Python in the browser via Pyodide; **Mode C** transcribes the
    app to native JavaScript at build time. Neither needs a runtime Python extra —
    the static bundling is done by the CLI (the `cli` extra). Only **Mode B**
    (server) needs the `server` extra.

!!! tip "Using `uv`?"
    `uv add tempestweb` (or `uv add "tempestweb[server,cli]"`) works the same and
    is faster, with a reproducible lockfile.

## Create your first project

Installed the `cli`? Then **don't hand-write the files** — the CLI scaffolds a
runnable project for you:

```bash
tempestweb new todolist       # creates the todolist/ folder with a working counter
cd todolist
tempestweb dev                # serves at http://127.0.0.1:8000 with hot-reload
```

`tempestweb new` writes four files:

```text
todolist/
├── app.py              # the UI: exposes make_state() and view() — the starter counter
├── tempestweb.toml     # project config (name, entrypoint, default mode/port)
├── README.md
└── .gitignore
```

!!! question "Does the file **have** to be named `app.py`?"
    By default, yes — the CLI looks for `app.py` at the project root. But the name
    is **configurable**: `tempestweb.toml` points at the entrypoint, so you can
    rename it.

    ```toml
    [project]
    name = "todolist"
    entrypoint = "app.py"   # change to "main.py", "src/app.py", etc.
    ```

    The only requirement is that this module exposes **two** callables:
    `make_state()` (the initial state) and `view(app)` (the widget tree). Without
    them the build fails with `must define a callable make_state/view`.

!!! tip "No `tempestweb.toml`?"
    It still works — every field has a default (`entrypoint = "app.py"`,
    `mode = "wasm"`, port 8000). `tempestweb.toml` is only needed to **change** a
    default. If you created the project by hand with just an `app.py`,
    `tempestweb build --mode wasm` already runs.

### CLI commands

Each takes the project **directory** via `--path` (default: current directory) —
never a positional `.py` file.

| Command | What it does |
|---|---|
| `tempestweb new <name>` | Scaffold a runnable project (counter + `tempestweb.toml`). |
| `tempestweb dev --mode <wasm\|server\|transpile>` | Develop locally with watch + reload — **serves every mode**, including **Mode B (server)**. |
| `tempestweb build --mode <wasm\|server\|transpile>` | Emit the artifact to `dist/<mode>/`. |
| `tempestweb run --mode <wasm\|server\|transpile>` | Serve the app **as built, no watcher** (production-like). |
| `tempestweb sync` | Fill `[wasm].modules` from the installed pure-Python dependencies. |
| `tempestweb deploy` | Write the Mode B deploy files (nginx + Docker + guide). |
| `tempestweb vapid` | Generate VAPID keys for Web Push. |
| `tempestweb lint` | Run `ruff check` on your project (report only). |
| `tempestweb fix` | Apply `ruff` autofixes and reformat (writes). |
| `tempestweb format` | Format the code with `ruff format` (writes). |
| `tempestweb fmt-check` | Check formatting with `ruff format --check` (read-only). |
| `tempestweb type` | Run type checking with `mypy`. |
| `tempestweb test` | Run the suite with `pytest` (no tests = success). |
| `tempestweb check` | Quality gate: ruff → format → mypy → pytest, stops at 1st error. |

!!! tip "`dev` to develop, `run` to serve"
    `tempestweb dev` runs any mode locally with watch + reload — including **Mode
    B** (Python on the server, FastAPI + WebSocket), which rebuilds and restarts
    the server on every edit:

    ```bash
    tempestweb dev --mode wasm       # Mode A (default): Python in the browser
    tempestweb dev --mode server     # Mode B: FastAPI + uvicorn, restart on save
    tempestweb dev --mode transpile  # Mode C: native JS, live-reload
    ```

    `tempestweb run` instead builds once and serves **without a watcher** — the
    production-like path (it's what the `tempestweb deploy` Dockerfile runs).

Want the full walkthrough of each subcommand? See
[Using the CLI](cli.md). Or jump straight into the [Tutorial](tutorial/index.md). 🚀

---

## Installing to contribute

The rest of this page is for those who will **develop tempestweb itself**: run the
quality gate, the tests, and build this documentation. For that the project uses
[`uv`](https://docs.astral.sh/uv/) for the Python environment and `npm` only for
the JS client's test tooling (jsdom).

### Contributor prerequisites

- **Python 3.11+** (the repository runs on 3.13).
- **[uv](https://docs.astral.sh/uv/)** — installer and venv manager.
- **Node.js 18+** — only for the client's `node --test` (jsdom).

!!! tip "Why `uv`?"
    `uv` creates the venv and installs dependencies in seconds, with a
    reproducible lockfile (`uv.lock`). It is the project's default manager.

### Clone and install

```bash
git clone https://github.com/mauriciobenjamin700/tempestweb.git
cd tempestweb
make setup
```

The `make setup` target does three things:

```bash
uv venv                                  # (1) create .venv
uv pip install -e ".[dev,server,cli]"    # (2) install the package + extras
npm install                              # (3) JS test tooling
```

Here the install is **editable** (`-e`) and includes the development extras
`dev` (ruff, mypy, pytest) and `docs` (mkdocs), on top of the runtime extras
`server` and `cli` already described [above](#install-from-pypi).

### Run the gate

Before any commit, the project requires the full gate to pass:

```bash
make check
```

This runs, in order:

```bash
ruff check . && ruff format --check .   # lint + format (double quotes, ANN, D)
mypy tempestweb                         # strict typing
pytest -q                               # Python tests
node --test "tests/client/**/*.test.js" # client tests (jsdom)
```

!!! check "All green?"
    If `make check` finishes without errors, your environment is ready. 🎉

### Build this documentation

The documentation is a bilingual MkDocs site. To install and build it locally:

```bash
uv pip install -e ".[docs]"
uv run mkdocs build --strict   # fails on ANY warning — that is the gate
uv run mkdocs serve            # local preview at http://127.0.0.1:8000
```

!!! warning "`mkdocs serve` is local preview only"
    The published site lives on **GitHub Pages**, auto-deployed via
    `.github/workflows/docs.yml`. The official links are
    [the PT version](https://mauriciobenjamin700.github.io/tempestweb/) and
    [the EN version](https://mauriciobenjamin700.github.io/tempestweb/en/) —
    never `localhost`.

### Recap

- **Use:** `pip install tempestweb` (plus optional extras). Only Python needed.
- **Contribute:** `git clone` + `make setup` creates the venv and installs
  everything (Python + JS tooling); needs `uv` and Node.
- Extras control which modes/capabilities you enable.
- `make check` is the gate; `uv run mkdocs build --strict` is the docs gate.

Ready? Head to the [Architecture](architecture.md) or jump straight into the
[Tutorial](tutorial/index.md). 🚀
