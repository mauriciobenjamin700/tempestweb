# REVIEW-T5 — adversarial QA (re-QA after fix round 1)

**Track:** T5 — `feat/cli-devloop` (`tempestweb/cli/*`, `tempestweb/devserver/*`)
**Reviewer:** tw-qa (skeptical, run-not-trust)
**Date:** 2026-06-11
**VERDICT: PASS**

## Gate (run from the project `.venv`, clean state)

| Step | Command | Result |
|---|---|---|
| Lint | `.venv/bin/ruff check .` | `All checks passed!` (exit 0) |
| Format | `.venv/bin/ruff format --check .` | `32 files already formatted` (exit 0) |
| Types | `.venv/bin/mypy tempestweb` | `Success: no issues found in 19 source files` (exit 0) |
| Python tests | `.venv/bin/pytest -q` | `69 passed in 1.29s` (exit 0) |
| JS tests | `node --test "tests/client/**/*.test.js"` | `pass 1, fail 0` (exit 0) |

Gate config is genuinely strict and enforces the standard: ruff `select` includes
`ANN` (annotations) + `D` (google docstrings) + `Q` (double quotes);
`mypy strict = true`. Tests are exempt from `D`/`ANN` only (per-file-ignores), the
intended posture.

## Done-when checklist (each clause tied to a passing proof)

### 1. `tempestweb new X` creates a runnable project tree — PASS
- Verified end-to-end with the **installed console script** (`.venv/bin/tempestweb new myapp`):
  writes `app.py`, `tempestweb.toml`, `README.md`, `.gitignore`; exit 0.
- "Runnable" is not just asserted in prose: `create_project(..., verify=True)` loads the
  scaffolded `app.py` and reconciles its initial view into a real core `Node`. I reproduced
  this independently — `render_initial_tree(load_app(".../myapp/app.py"))` returns a `Column`.
- Tests: `test_cli_scaffold.py` (10 tests incl. `test_create_project_verifies_runnable`,
  `test_scaffold_app_py_defines_contract`, refusal/force/empty-dir cases),
  `test_cli.py::test_new_dispatch_creates_project`, `test_new_dispatch_reports_failure`.

### 2. Dev watcher detects a change and emits a reload — PASS (incl. real-FS proof)
- `test_cli_devserver.py::test_watcher_run_reloads_on_real_file_write` drives the
  **production** `_watchfiles_stream` (real `watchfiles.awatch`, polling backend) against a
  real on-disk write and asserts a `ReloadEvent` lands. **This test executed (not skipped)** —
  `watchfiles` is installed in the venv; confirmed via `pytest -v` (13/13 passed, the
  real-file-write case shows PASSED).
- Injected-stream coverage too: `test_watcher_run_consumes_stream`, `handle_batch`
  suffix-filtering, relativize/sort, custom suffixes; signal pub/sub + generation +
  unsubscribe + async `wait`. `create_dev_session` wiring proven to reach the transport
  (`test_dev_session_*`).
- `_cmd_dev`'s blocking `asyncio.run(...)` and `KeyboardInterrupt` branch are
  `# pragma: no cover - interactive only` — honest: the loop body (`watcher.run`) is itself
  covered by the real-FS test, and dispatch is covered via monkeypatched `asyncio.run`
  (`test_dev_dispatch_runs_watch_loop`).

### 3. `build --mode` produces the expected artifact layout — PASS
- Verified end-to-end via the installed CLI for **both** modes. wasm artifact:
  `index.html`, `bootstrap.js`, `app.py`,
  `client/{tempestweb,dom,style,events,transport,transport-wasm}.js`. server artifact:
  `server.py`, `app.py`, `static/{...,transport-ws}.js`. The shared `client/` dir actually
  contains every asset the builder copies (checked) — build is not copying phantom files.
- Build gates on real renderability (`load_app` + `render_initial_tree`); a broken `app.py`
  raises `BuildError` (`test_build_unrunnable_project_raises`,
  `test_build_dispatch_reports_failure`). Layout pinned by `WASM_ARTIFACT_FILES` /
  `SERVER_ARTIFACT_FILES` and asserted file-by-file (`test_cli_build.py`, 11 tests).
- `run` = build + bind plan (`test_cli_run.py`, `test_run_dispatch_builds_and_plans`).

## Adversarial findings

- **No `_core` edits.** `git diff --name-only main...HEAD | grep _core` → empty.
- **No out-of-track files.** Every changed path is under `tempestweb/cli/*`,
  `tempestweb/devserver/*`, `tests/unit/test_cli*.py`, or the track's own `*-T5.md` docs.
  `tempestweb/cli/main.py` (the CLI parser) is in-scope; the **repo-top** `main.py` /
  `tempestweb/main.py` were NOT touched (MANIFEST's "exceto main.py topo").
- **No skipped/xfail/assert-True/empty tests.** Only conditional guard is
  `requires_watchfiles`, which did not trigger (dep present) — real coverage, not a hidden skip.
- **The `NotImplementedError` (server.py `run`) and `throw new Error` (bootstrap.js `boot`)
  live in GENERATED ARTIFACT TEMPLATES**, not in T5's own runtime logic, and are explicitly
  scoped to Tracks T2/T3 in docstrings + `NOTES-T5.md`. The done-when is "artifact layout",
  which the build satisfies; serving is correctly out of scope. Honest, not overclaimed.
- **Quotes:** no real single-quote violations. Apparent grep hits are apostrophes in docstring
  prose and `'''`-delimited templates whose embedded file bodies contain double quotes
  (ruff `flake8-quotes` passes, incl. avoid-escape).
- **Re-exports complete** (`cli/__init__.py`, `devserver/__init__.py`, `commands/__init__.py`
  all aggregate with `__all__`), full typing + google docstrings throughout (mypy strict +
  ruff D/ANN green).

## Gaps

None blocking. Minor (not required by the done-when, noted for the morning merge):
- The generated artifacts' transport glue (Pyodide bootstrap, FastAPI WS host) are stubs by
  design — real behavior arrives on the T2/T3 merge; layout is what T5 promised and delivers.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
