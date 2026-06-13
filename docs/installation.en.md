# Installation

Let's get tempestweb running locally. The project uses
[`uv`](https://docs.astral.sh/uv/) for the Python environment and `npm` only for
the JS client's test tooling (jsdom). No frontend build step — the client is
plain JavaScript. ✅

## Prerequisites

- **Python 3.11+** (the repository runs on 3.13).
- **[uv](https://docs.astral.sh/uv/)** — installer and venv manager.
- **Node.js 18+** — only for the client's `node --test` (jsdom).

!!! tip "Why `uv`?"
    `uv` creates the venv and installs dependencies in seconds, with a
    reproducible lockfile (`uv.lock`). It is the project's default manager.

## Clone and install

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

The **extras** decide which capabilities you install:

| Extra | For |
|---|---|
| `dev` | ruff, mypy, pytest — the quality gate. |
| `server` | FastAPI, uvicorn, websockets — **Mode B**. |
| `cli` | watchfiles + tomlkit — the dev loop (`tempestweb dev`) and `tempestweb sync`. |
| `docs` | mkdocs-material + i18n — **this documentation**. |

!!! note "Mode A (WASM) has no Python extra"
    Mode A runs Python in the browser via Pyodide; the static bundling is done
    by the CLI. You do not need a Python extra for it.

## Run the gate

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

## Build this documentation

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

## Recap

- `make setup` creates the venv and installs everything (Python + JS tooling).
- Extras control which modes/capabilities you enable.
- `make check` is the gate; `uv run mkdocs build --strict` is the docs gate.

Ready? Head to the [Architecture](architecture.md) or jump straight into the
[Tutorial](tutorial/index.md). 🚀
