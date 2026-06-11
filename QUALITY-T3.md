# QUALITY-T3.md — code-quality pass on track T3 (`feat/mode-wasm`)

Branch raised to the tempest-fastapi-sdk / tempestroid bar. The build agent had
already produced very high-quality code (Google docstrings on every public
surface, full annotations, double quotes, module-level re-exports + `__all__`,
empty-collection idioms, async-first). The gate was green on arrival and stayed
green.

## Applied (quality only, no behavior change)

- **`tempestweb/runtime/wasm.py` — hoisted a function-local import to module
  level.** `WasmRuntime.run()` imported `TransportClosedError` inside the method
  body (`from tempestweb.transports.base import TransportClosedError`). The module
  already imports `Event`/`PatchTransport`/`Patch` from the same module at the
  top, so the lazy import was an unnecessary deviation from the "imports at module
  level" idiom (there is no import cycle that would justify it — `transports.base`
  has no dependency back on `runtime.wasm`). Moved `TransportClosedError` into the
  existing top-level `from tempestweb.transports.base import (...)` group and
  removed the in-method import. Behavior identical; `ruff check` (incl. import
  order/unused), `ruff format --check`, `mypy --strict`, and all 25 Python tests +
  6 JS tests remain green.

## Verified clean — no change needed

- `tempestweb/transports/wasm.py`, `tempestweb/runtime/wasm_main.py`,
  `client/transport-wasm.js`, and all three `tests/unit/test_wasm_*.py` already
  meet the bar (docstrings, typing, JSDoc, double quotes, idioms). No edits.
- `public/index.html` retains `console.log`/`console.warn` calls. These are **not**
  leftover debug noise: they are the documented diagnostic output of the live
  Mode-A bootstrap's fallback path (when T1's DOM renderer is not yet merged, the
  wire traffic is logged to *prove* that Pyodide + pydantic_core ran in the browser
  and produced patches — see the inline comments and `NOTES-T3.md`). Left in place
  deliberately; removing them would weaken the manual-verification path that A0/A1
  depend on.
- `tempestweb/transports/base.py` is the shared seam (owned by T2, consumed by
  T3). Not in this track's file set — left untouched.

## Deferred (would require a behavior change — out of scope for a quality-only pass)

- **`WasmRuntime._apply_patches` uses `asyncio.ensure_future(...)` and discards the
  returned task.** This is the well-known asyncio "fire-and-forget" footgun: a task
  with no strong reference can be garbage-collected mid-flight before it completes,
  and any exception it raises is only surfaced at GC time (a logged
  "Task exception was never retrieved" warning, not a propagated error). Hardening
  this correctly means changing observable behavior and lifecycle — e.g. keeping
  the task in a `set[asyncio.Task[None]]` on the instance with a
  `task.add_done_callback(self._tasks.discard)` cleanup, and deciding how delivery
  errors should propagate/teardown. Because that alters scheduling/error semantics
  (and the public surface would gain a task registry), it is left for the build
  owner / supervised integration rather than applied here. The current code is
  correct for the happy path the tests exercise; this is a robustness note, not a
  live bug in the tested flows.

## Gate (post-pass, all green)

```
uv run ruff check  tempestweb/{transports,runtime}/wasm*.py tests/unit/test_wasm_*.py   # All checks passed!
uv run ruff format --check ...                                                           # already formatted
uv run mypy tempestweb                                                                   # Success: no issues found in 12 source files
uv run pytest tests/unit/test_wasm_main.py tests/unit/test_wasm_runtime.py tests/unit/test_wasm_transport.py -q   # 25 passed
node --test tests/client/transport-wasm.test.js                                          # 6 pass / 0 fail
```
