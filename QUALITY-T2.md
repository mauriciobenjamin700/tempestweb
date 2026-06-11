# Quality pass — Track T2 (`feat/mode-server`)

Code-quality enforcement pass against the tempest-fastapi-sdk / tempestroid bar.
Quality-only fixes were applied; no behavior or public signatures changed beyond
re-exports. Branch stayed green throughout.

## Gate result (T2-owned files only)

T2 owns: `tempestweb/server/*`, `tempestweb/transports/{base,websocket,sse}.py`,
`tempestweb/runtime/{session,serialize}.py` + their `__init__.py`,
`client/transport-{ws,sse}.js`, `tests/unit/test_server*.py` (+ the JS transport
tests under `tests/client/`).

- `ruff check` — All checks passed (select E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D).
- `ruff format --check` — 9 files already formatted.
- `mypy --strict` — Success: no issues found in 9 source files.
- `pytest tests/unit/test_server_{native,sse,ws}.py` — 9 passed.
- `node --test tests/client/transport-{ws,sse}.test.js` — 9 passed.

## Applied fixes

1. **Re-export `NativeCallError` at module level**
   (`tempestweb/runtime/__init__.py`). `NativeCallError` is a public exception
   raised by `AppSession.native_call` and was already in `session.py`'s `__all__`,
   but the package `__init__` did not surface it — violating the global "every
   public resource is importable from the module level via `__init__`" idiom.
   Added the import and the `__all__` entry. No behavior change (additive
   re-export only); `from tempestweb.runtime import NativeCallError` now works.

## Reviewed and found already at the bar (no change needed)

- **Google docstrings** on every public class/method/function across all nine
  Python modules, in English, covering Args/Returns/Raises/Yields. Module
  docstrings describe the seam and reference `docs/contract.md`.
- **Full type annotations**; the three intentional `# noqa: ANN401` sites
  (`encode_native_result.value`, `AppSession.native_call` return,
  `serialize._json_safe`) are correctly justified — the value type genuinely
  varies with the proxied capability / arbitrary IR prop. `cast("Callable[...]",
  ...)` used idiomatically in `resolve_handler`.
- **Idioms**: module-level re-exports with `__all__` everywhere; `select()` n/a
  (no SQLAlchemy in this track); async-first I/O; `contextlib.suppress` for
  cancellation; structured-concurrency task tracking; `runtime_checkable`
  Protocol for the transport seam; `Generic[S]` for the per-connection state
  type. Naming follows the convention (`WebSocketTransport`, `SSETransport`,
  `AppSession`, `TempestWebServer`).
- **JS client**: plain JS (no TS/framework/build), double quotes, ES modules,
  complete and accurate JSDoc on every public function and returned-object
  method, injectable `WebSocketImpl`/`EventSourceImpl`/`fetchImpl` for jsdom
  tests, no dead code, no leftover `console.log`. The empty `ping` listener in
  `transport-sse.js` is intentional (documented heartbeat no-op), not dead code.

## Deferred — would require a behavior change (NOT done in this pass)

None. No quality issue found in this track requires a behavior or public-signature
change. The single applied fix was an additive re-export. There is nothing to
defer.

### Observations for the supervised merge (informational, out of scope here)

These are not defects in T2's code and were intentionally left untouched because
acting on them changes behavior or touches a published surface:

- `tests/unit/test_server_*.py` emit a Starlette deprecation warning
  (`Using httpx with starlette.testclient is deprecated; install httpx2`). This
  comes from the FastAPI `TestClient`, not from T2 code. Silencing or migrating
  the test client is a dependency/behavior decision for the author.
- The `# pragma`-free broad `except (..., Exception)` in
  `AppSession.close` / `WebSocketTransport.close` is deliberate (swallow any
  teardown errors during structured-concurrency cancellation). Left as-is — it is
  the correct shutdown posture, not a lint smell.
