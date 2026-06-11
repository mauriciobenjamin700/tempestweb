# REVIEW-T3 — adversarial QA, track T3 (`feat/mode-wasm`)

**VERDICT: PASS**

Reviewer: tw-qa (skeptical). Date: 2026-06-11. Branch: `feat/mode-wasm` @ `e7471ed`.
Re-QA after fix round 1 (prior verdict was PASS-WITH-GAPS @ `2d7b51c`).

## Summary

The two gaps from round 1 are genuinely closed and verified by a passing test —
not by prose. The stale `public/manifest.json` (it was missing
`tempestweb/runtime/wasm_main.py`, which would have crashed the live bootstrap with
`ModuleNotFoundError` before producing any IR) is regenerated: the committed
manifest now lists `wasm_main.py` at line 53 and equals `gen_manifest.collect()`
**exactly** (57 entries == 57). A new headless test,
`tests/unit/test_wasm_bootstrap_contract.py`, locks this so it cannot drift again,
and also pins the JS-facing Python symbols `index.html` calls (`make_state`/`view`
on the app module; `initial_node_json`/`push_event_json`/`close` on
`WasmAppHandle`; `bootstrap`). The full gate is green from a clean state (ruff,
ruff format `--check`, mypy `--strict`, 32 pytest, 7 jsdom). `tempestweb/_core/**`
is untouched and no other track's files were edited. No skips, no xfail, no
assert-nothing, no `NotImplementedError` behind a green test. The pure-Python
units and the JS transport test are real and content-asserting.

The done-when is met: the transports implement the interface, the bootstrap is
complete (manifest now correct) and documented (`index.html` + NOTES-T3.md), the
pure-Python units are green, and the live Pyodide run is documented in NOTES-T3.md
(correctly flagged manual — no browser in CI). Graded PASS. One non-blocking
correctness note on the live-only teardown path is recorded below for integration.

## Gate output (run from clean state — `make check`)

```
.venv/bin/ruff check .              → All checks passed!                    (exit 0)
.venv/bin/ruff format --check .      → 23 files already formatted            (exit 0)
.venv/bin/mypy tempestweb            → Success: no issues found in 12 files  (exit 0)
.venv/bin/pytest -q                  → 32 passed in 0.16s                    (exit 0)
node --test tests/client/**/*.test.js → 7 pass / 0 fail / 0 skipped         (exit 0)
MAKE_CHECK_EXIT=0

pytest tests/unit/test_wasm*.py      → 28 passed                            (exit 0)
manifest == gen_manifest.collect()   → EQUAL: True (57 == 57)               (verified)
git diff main..HEAD -- tempestweb/_core → (empty — _core untouched)
```

## Done-when checklist

| Clause | Status | Evidence |
|---|---|---|
| `transport-wasm.js` implements the interface | PASS | `tests/client/transport-wasm.test.js` (7 tests): rejects bad bridge, deliver→onPatches, pre-registration buffering+flush-in-order, sendEvent→pushEvent, close stops delivery + drops handler + calls bridge.close, close idempotent. |
| `wasm.py` (transport) implements the interface | PASS | `test_wasm_transport.py`: `isinstance(t, PatchTransport)` via `@runtime_checkable`; deliver verbatim, empty no-op, FIFO queue, blocking recv, close unblocks recv with `TransportClosedError`, post-close raises on send/recv/push, idempotent close. |
| `wasm.py` (runtime) implements the interface | PASS | `test_wasm_runtime.py`: serialize_node shape/json/handler-null/style-lowering; serialize_patches update/insert/set_props handler-stripping; dispatch zero-arg / arg-payload / async / unknown-key / unknown-type; run() drains until closed (state==2). |
| Bootstrap is **complete** | **PASS (was GAP)** | `public/manifest.json` now includes `tempestweb/runtime/wasm_main.py` (line 53) and equals `gen_manifest.collect()` exactly. `test_committed_manifest_matches_collect` asserts it in CI. |
| Bootstrap is **documented** | PASS | `public/index.html` heavily commented; NOTES-T3.md A0 research + step-by-step manual run; SUMMARY-T3.md. |
| Pure-Python units green | PASS | 28 wasm tests + 4 others = 32, all green; every assertion checks state and/or patch/JSON content. |
| Live Pyodide run documented in NOTES-T3.md | PASS (documented) | NOTES-T3.md §"Manual verification": serve→open→splash→console `initial node`/`patch batch`→no-network check. NOT executed (no browser in CI) — correctly flagged manual. Now passes-as-written since the manifest gap is fixed. |
| Manifest-equality regression test (round-1 LOW) | PASS (added) | `test_wasm_bootstrap_contract.py::test_committed_manifest_matches_collect` + `_app_module_exposes_bootstrap_entrypoints` + `_wasm_app_handle_exposes_js_contract`. |

## Findings (prioritized)

1. **[LOW — live-only, unverified path] `WasmAppHandle.close` is `async def`, but
   `public/index.html` calls `pyHandle.close()` synchronously (line 151) without
   awaiting.** In Pyodide a Python coroutine function returns a JS Promise that
   `index.html` discards, so `await self._transport.close()` and `self._task.cancel()`
   in `wasm_main.py` (lines 88–91) would not run eagerly on teardown. This is a
   best-effort-cleanup concern only on the browser path (the page is unloading
   anyway), and the headless test `test_close_stops_the_event_loop` `await`s it so
   the Python logic is proven correct. It does not affect the steady-state
   counter loop or any done-when clause. **Recommendation at T1 integration:** make
   `bridge.close` in `index.html` do `pyHandle.close()` and let Pyodide schedule it
   (or make the handle's `close` sync), and document the unload semantics. Not a
   blocker for T3 as scoped.

2. **[INFO — expected, correctly disclosed] The visible counter requires T1.**
   `index.html` falls back to console-logging wire traffic when `client/tempestweb.js`
   (T1's DOM renderer) is a stub. Honestly documented as a merge-order dependency in
   NOTES-T3.md, not overclaimed. Not a defect against T3's scope.

3. **[INFO — all changes in-track] The branch's diff vs `main` touches only T3's
   declared directories:** `tempestweb/runtime/*`, `tempestweb/transports/wasm.py`
   (+ `__init__` re-exports), `client/transport-wasm.js`, `public/*`,
   `tests/unit/test_wasm*`, `tests/client/transport-wasm.test.js`, plus T3 doc files
   (NOTES/QUALITY/REVIEW/SUMMARY-T3.md). `_core` untouched; no other track's files
   edited. Compliant.

## Convention scan (CLAUDE.md)

- Double quotes, full type hints, Google docstrings (EN): PASS across all four
  Python modules and the four test files (ruff `ANN`+`D` + mypy `--strict` enforce
  it and are green).
- JS: plain ES modules, JSDoc on the public `createWasmTransport`/`WasmBridge`, no
  TypeScript, no build step, no runtime deps (only `jsdom` devDep for tests). PASS.
- `__init__.py` re-exports with `__all__`: PASS (`runtime`, `transports`).
- Collections-return-`[]` convention: N/A to this track (no list endpoints).

## Bottom line

Ship it. Both round-1 gaps are closed with real, passing tests; the gate is green
from clean; the contract conformance (handler→null, `{type,key,props,children}`,
Style/Edge lowering) is genuinely asserted; `_core` is untouched and the scope is
clean. The only residual item is a live-only teardown nit (finding #1) to settle
when T1's renderer is wired in — it does not contradict any done-when clause.
