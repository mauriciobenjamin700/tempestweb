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

Done — jump straight into the [Tutorial](tutorial/index.md). 🚀

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
