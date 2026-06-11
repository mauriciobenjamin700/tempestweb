# SUMMARY — Track T5 (CLI + dev loop)

Branch: `feat/cli-devloop`

## Scope delivered

Fleshed out `tempestweb/cli/` and `tempestweb/devserver/` so the full developer
loop works in typed Python, with pytest coverage. All gates green
(`ruff check`, `ruff format --check`, `mypy --strict`, `pytest`).

### `tempestweb/cli/`

- **`main.py`** — keeps the original parser shape (`args.command` + `args.mode`)
  and now **dispatches** `new` / `dev` / `build` / `run` to their command
  entrypoints. Added non-breaking flags: `new --into/--force/--no-verify`,
  `dev --path`, `build --path/--out`, `run --path/--host/--port`. Console script
  `tempestweb = tempestweb.cli.main:main` works end to end.
- **`scaffold.py`** — `scaffold_project()` / `render_files()` write a minimal but
  *runnable* tree: `app.py` (working counter using the `make_state` / `view`
  contract against the vendored core), `tempestweb.toml`, `README.md`,
  `.gitignore`. Refuses a non-empty target unless `force=True`.
- **`config.py`** — `load_config()` reads `tempestweb.toml` (name, entrypoint,
  mode, host, port) with full defaults when absent; validates the mode.
- **`loader.py`** — `load_app()` imports a project entrypoint, validates the
  `make_state` / `view` contract; `render_initial_tree()` reconciles the initial
  view into a core `Node` (cheapest proof a project is runnable).
- **`commands/new.py`** — `create_project()` scaffolds, then (default) verifies
  the scaffold renders.
- **`commands/build.py`** — `build_artifact()` emits the mode-specific layout:
  - **wasm** (PWA app-shell base for T9): `index.html` + `bootstrap.js` +
    `app.py` + `client/{tempestweb,dom,style,events,transport,transport-wasm}.js`.
  - **server**: `server.py` + `app.py` + `static/{...,transport-ws}.js`.
  A build only succeeds if the project renders; output dir defaults to
  `<project>/dist/<mode>` and is cleaned first.
- **`commands/dev.py`** — `create_dev_session()` wires watcher + signal + a
  transport-agnostic `StubTransport` reload sink.
- **`commands/run.py`** — `prepare_run()` = build + bind plan (`RunPlan.url`).

### `tempestweb/devserver/` (transport-agnostic)

- **`reload.py`** — `ReloadSignal` pub/sub hub (`subscribe`/`trigger`/`wait`),
  `ReloadEvent` (kind/paths/generation), `ReloadKind` (`RESTART` default,
  `RELOAD` reserved).
- **`watcher.py`** — `FileWatcher` turns filesystem changes into reload events,
  filtering by suffix (`.py/.html/.css/.js`) and relativizing paths. Default
  stream is the `watchfiles.awatch` adapter `_watchfiles_stream`; tests also
  inject a deterministic async stream for the suffix/relativize/dedup logic.
  The production factory is covered by `test_watcher_run_reloads_on_real_file_write`,
  which drives `watcher.run(stream_factory=_watchfiles_stream)` against a real
  `tmp_path` file write (polling backend forced so the loop is deterministic on
  any filesystem, incl. WSL/network mounts).

## Bugs fixed while building

- **Scaffold loader crash**: a scaffolded `app.py` using `@dataclass` under
  `from __future__ import annotations` raised `AttributeError: 'NoneType' has no
  __dict__` because the synthetic module was not in `sys.modules` when the
  dataclass resolved its field types. `loader.py` now registers the module
  (under a path-hash-unique name, so multiple projects load independently)
  before `exec_module`, and pops it on failure.
- Lint/type gate: `Callable` from `collections.abc` (UP035);
  `ReloadKind(StrEnum)` matching the vendored core (UP042); TOML template
  double-quoted (Q001); `ConfigError` added to `config.__all__`;
  `create_dev_session` typed `str | Path` (mypy arg-type).

## Verification (all green)

    ruff check tempestweb tests        # All checks passed
    ruff format --check tempestweb tests
    mypy tempestweb                    # Success: no issues found in 19 source files
    pytest -q                          # 68 passed
    pytest tests/unit/test_cli*.py -q  # 66 passed (the track gate)

DONE-WHEN, confirmed by automated tests:
- `tempestweb new X` creates a runnable project tree.
- dev watcher detects a change and emits a reload — covered by injected-stream
  tests (`handle_batch` / `run`) **and** a real-file integration test that drives
  the production `_watchfiles_stream` factory through `watcher.run` (no manual
  step needed; see `test_watcher_run_reloads_on_real_file_write`).
- `build --mode wasm|server` produces the expected artifact layout.

## What is stubbed (owned by other tracks — clearly marked in code)

- **wasm `bootstrap.js`** is an app-shell placeholder; live Pyodide load/mount is
  **Track T3** (Mode A). The artifact layout is final and is the PWA app-shell
  base **T9** builds on.
- **server `server.py`** exposes a `run()` that raises `NotImplementedError`; the
  live FastAPI + WebSocket host is **Track T2** (Mode B).
- **`dev` reload transport** is `StubTransport` (records reloads). Real reload
  delivery (browser tab reload for A; session restart + push for B) plugs into
  the same `ReloadSignal` and is owned by **T3 / T2**.
- **`run` serving** stops at "artifact built + bind plan ready"; serving is the
  transports' job (T2 / T3).

## Needs manual verification by a human

- Nothing blocking for T5's scope. The non-automatable bit is the *visual* result
  of a real wasm boot in a browser (Pyodide) — that belongs to T3/T9 once their
  transports land. The wasm artifact's structure is asserted by
  `test_cli_build.py`.
- The repo-level `node --test tests/client/` *directory* invocation fails to
  resolve the path on this Node version (pre-existing, untouched by T5);
  `node --test tests/client/smoke.test.js` passes. Flagging for whoever owns the
  JS test runner config.

## Suggested merge order

T5 is self-contained (depends only on the vendored `_core` and the existing
`client/` assets) with no runtime coupling to T2/T3, so it can merge early.
Recommended: **merge T5 before T2/T3/T9** — those tracks then replace the
clearly-marked stubs (`bootstrap.js`, `server.py`, `StubTransport`,
`run`-serving) against the artifact layout and `ReloadSignal` seam T5 pins here.

## Commits on this branch (T5 work)

- `fix(T5): clear lint/typing gate + package re-exports`
- `feat(T5): dispatch CLI subcommands + fix scaffold loader import`
- `test(T5): cover cli + devserver end to end`
- `docs(T5): add SUMMARY-T5.md`
