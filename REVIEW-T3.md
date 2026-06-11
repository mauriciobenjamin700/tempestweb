# REVIEW-T3 — adversarial QA, track T3 (`feat/mode-wasm`)

**VERDICT: PASS-WITH-GAPS**

Reviewer: tw-qa (skeptical). Date: 2026-06-11. Branch: `feat/mode-wasm` @ `2d7b51c`.

## Summary

All automated gates are green from a clean state (ruff, ruff format, mypy
`--strict`, 29 pytest, 7 jsdom). The pure-Python units and the JS transport test
are real, meaningful tests — no skips, no xfail, no assert-nothing, no
`NotImplementedError` behind a green test. `tempestweb/_core/**` is untouched and
no other track's files were edited. The serialization conformance to the golden
fixtures (`{type,key,props,children}`, handlers → `null`) is verified.

**But there is one real defect that breaks the done-when's "the bootstrap is
complete" claim:** `public/manifest.json` is stale — it is missing
`tempestweb/runtime/wasm_main.py`. The live browser bootstrap (`public/index.html`)
runs `from tempestweb.runtime import bootstrap`, whose `__init__.py` imports
`from tempestweb.runtime.wasm_main import ...`. Since `wasm_main.py` is never
written into the Pyodide FS, the bootstrap crashes with `ModuleNotFoundError`
**before producing any IR** — i.e. the manual verification steps in NOTES-T3.md
cannot succeed as committed. The pure-Python tests miss this because they import
from the local filesystem, not from the manifest-driven FS.

This is graded PASS-WITH-GAPS (not FAIL) because the automated done-when
(`pytest tests/unit/test_wasm*.py` green + manual steps documented) is satisfied,
and the bug is a one-line stale-artifact regression, not a logic defect — but the
"bootstrap is complete" half of the clause is not actually true as shipped.

## Gate output (run from clean state)

```
ruff check .            → All checks passed!                       (exit 0)
ruff format --check .    → 22 files already formatted              (exit 0)
mypy tempestweb          → Success: no issues found in 12 files    (exit 0)
pytest -q                → 29 passed in 0.16s                      (exit 0)
pytest tests/unit/test_wasm*.py → 25 passed                        (exit 0)
node --test tests/client/**/*.test.js → 7 pass / 0 fail            (exit 0)
```

## Done-when checklist

| Clause | Status | Evidence |
|---|---|---|
| `transport-wasm.js` implements the interface | PASS | `tests/client/transport-wasm.test.js` (6 tests): rejects bad bridge, deliver→onPatches, pre-registration buffering+flush-in-order, sendEvent→pushEvent, close stops delivery + idempotent. |
| `wasm.py` implements the interface | PASS | `test_wasm_transport.py` proves `isinstance(t, PatchTransport)`; deliver, empty no-op, queue order, blocking recv, close unblocks, post-close raises, idempotent close. |
| Bootstrap is **complete** | **GAP** | `public/manifest.json` omits `tempestweb/runtime/wasm_main.py` → live `import tempestweb.runtime` raises `ModuleNotFoundError`. Regenerating gives 57 files vs committed 56; the one diff is exactly `wasm_main.py`. |
| Bootstrap is **documented** | PASS | `public/index.html` heavily commented; NOTES-T3.md A0 research + step-by-step manual run; SUMMARY-T3.md. |
| Pure-Python units green | PASS | 25 wasm tests + 4 others, all green; serialize/dispatch/run/round-trip all asserted with state and patch-content checks. |
| Live Pyodide run documented in NOTES-T3.md | PASS (documented) | NOTES-T3.md §"Manual verification" has serve→open→console-log steps. NOT executed (no browser in CI) — correctly flagged manual. Will fail as written until the manifest gap is fixed (see below). |

## Findings (prioritized)

1. **[HIGH — breaks the live bootstrap] Stale `public/manifest.json` missing
   `tempestweb/runtime/wasm_main.py`.** The committed manifest (56 entries) was
   generated before `wasm_main.py` was added. `public/index.html`'s
   `writePackageToFS` only writes files listed in the manifest, so in the browser
   `from tempestweb.runtime import bootstrap` (run at line ~103 of index.html, via
   `runtime/__init__.py` re-export of `wasm_main`) raises `ModuleNotFoundError:
   tempestweb.runtime.wasm_main`. The manual steps in NOTES-T3.md therefore cannot
   pass as committed.
   - **Proof:** `python3 public/gen_manifest.py` regenerates a 57-file list; `diff`
     vs committed shows the single added line `tempestweb/runtime/wasm_main.py`.
   - **Fix (one line of regeneration):** run `python public/gen_manifest.py` and
     commit the updated `public/manifest.json`. Better: add a tiny test that asserts
     the committed manifest equals `gen_manifest.collect()` so this can never drift
     again (it would have caught this in CI). NOTES already says "regenerate if the
     file set changed" — it did change and wasn't regenerated.

2. **[LOW — no test guards manifest/bootstrap wiring] No automated check ties the
   manifest to the actual package file set, nor the bootstrap's referenced Python
   API (`make_state`, `view`, `bootstrap`, `push_event_json`, `initial_node_json`)
   to the entrypoint.** These are verified by hand here (example app exposes
   `make_state`/`view`; handle exposes the methods index.html calls) but a drift in
   any of them is invisible to the green gate. A cheap pytest that imports
   `gen_manifest.collect()` and compares to the JSON, plus one that asserts
   `examples.counter.app` has `make_state`/`view`, would close finding #1 and most
   of this.

3. **[INFO — expected, correctly disclosed] The visible counter requires T1.**
   `index.html` falls back to console-logging wire traffic when `client/tempestweb.js`
   (T1's DOM renderer) is a stub. This is honestly documented as a merge-order
   dependency, not overclaimed. Not a defect against T3's scope.

4. **[INFO — out-of-manifest-scope files, all in-track] T3 also added
   `tempestweb/runtime/wasm_main.py`, `public/gen_manifest.py`,
   `public/manifest.json`, `__init__.py` re-exports, and doc files.** All live
   inside T3's declared directories (`tempestweb/runtime`, `tempestweb/transports`,
   `client`, `public`, `tests/unit/test_wasm*`) — no other track touched. `_core`
   untouched. Compliant.

## Convention scan (CLAUDE.md)

- Double quotes, full type hints, Google docstrings (EN): PASS across all four
  Python modules and the three test files (ruff `ANN`+`D` + mypy strict enforce it
  and are green).
- JS: plain ES modules, JSDoc on the public `createWasmTransport`/`WasmBridge`, no
  TypeScript, no build step, no runtime deps. PASS.
- `__init__.py` re-exports with `__all__`: PASS (`runtime`, `transports`).
- Collections-return-`[]` convention: N/A to this track (no list endpoints).

## Bottom line

The code is clean and genuinely tested; the contract conformance is real. Ship it
only after regenerating `public/manifest.json` (finding #1) — until then the
"bootstrap is complete" claim is false and the documented manual Pyodide run will
`ModuleNotFoundError` on import. Add the manifest-equality test so it can't rot
again.
